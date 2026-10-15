"""Bounded raster decoding and content-addressed persistent image storage."""
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import re
import stat
import uuid
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 24_000_000
SIZES = {'full':1600,'large':512,'thumb':96}
FORMATS = {'JPEG':{'image/jpeg','image/jpg'},'PNG':{'image/png','image/x-png'},'WEBP':{'image/webp'}}


class MediaError(ValueError):
    """Safe, user-facing validation/storage failure."""


@dataclass(frozen=True)
class NormalizedImage:
    digest: str
    width: int
    height: int
    files: dict[str, bytes]


def normalize_image(stream, mime_type=None):
    data = stream.read(MAX_UPLOAD_BYTES+1)
    if not isinstance(data,bytes) or not data:
        raise MediaError('Bitte eine Bilddatei auswählen.')
    if len(data)>MAX_UPLOAD_BYTES:
        raise MediaError('Bilder dürfen höchstens 8 MB groß sein.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in FORMATS:
                    raise MediaError('Erlaubt sind JPEG, PNG und WebP.')
                if mime_type and mime_type not in {'application/octet-stream',*FORMATS[source.format]}:
                    raise MediaError('Dateiinhalt und angegebener Bildtyp stimmen nicht überein.')
                if max(source.size)>10000 or source.width*source.height>MAX_PIXELS:
                    raise MediaError('Das Bild ist zu groß. Erlaubt sind höchstens 24 Megapixel und 10.000 Pixel pro Seite.')
                if getattr(source,'n_frames',1)!=1:
                    raise MediaError('Bitte ein einzelnes Bild statt einer Animation auswählen.')
                source.load()
                oriented = ImageOps.exif_transpose(source).convert('RGBA')
                if oriented.getextrema()[3] == (255,255):
                    oriented = oriented.convert('RGB')
                # Copy only pixels: never retain EXIF, GPS, XMP, ICC or appended data.
                clean = Image.new(oriented.mode,oriented.size)
                clean.paste(oriented)
                clean.thumbnail((1600,1600),Image.Resampling.LANCZOS)
                files = {}
                for name,limit in SIZES.items():
                    image = clean.copy();image.thumbnail((limit,limit),Image.Resampling.LANCZOS)
                    output = BytesIO();image.save(output,format='WEBP',quality=88,method=4)
                    files[name] = output.getvalue()
                if len(files['full'])>MAX_UPLOAD_BYTES:
                    raise MediaError('Das aufbereitete Bild ist zu groß.')
                return NormalizedImage(sha256(files['full']).hexdigest(),clean.width,clean.height,files)
    except MediaError:
        raise
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning) as error:
        raise MediaError('Die Datei ist kein lesbares JPEG-, PNG- oder WebP-Bild.') from error


def media_directory(uploads_dir, digest, *, create=False):
    if not re.fullmatch(r'[0-9a-f]{64}',str(digest)):
        raise MediaError('Ungültige Bildkennung.')
    base = Path(uploads_dir).resolve()
    current = base
    for part in ('product-media',digest[:2],digest):
        current = current/part
        if current.is_symlink():
            raise MediaError('Der Bildspeicher enthält einen unzulässigen Verweis.')
        if create:
            current.mkdir(mode=0o700,parents=True,exist_ok=True)
        if current.exists() and (not current.is_dir() or not current.resolve().is_relative_to(base)):
            raise MediaError('Der Bildspeicher ist nicht verfügbar.')
    return current


def media_path(uploads_dir,digest,size='thumb'):
    if size not in SIZES:
        raise MediaError('Ungültige Bildgröße.')
    target = media_directory(uploads_dir,digest)/(size+'.webp')
    if target.is_symlink():
        raise MediaError('Der Bildspeicher enthält einen unzulässigen Verweis.')
    return target


def open_media(uploads_dir,digest,size='thumb'):
    path = media_path(uploads_dir,digest,size)
    descriptor = os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_CLOEXEC',0)|getattr(os,'O_NONBLOCK',0))
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor);raise MediaError('Das Bild ist nicht verfügbar.')
    return os.fdopen(descriptor,'rb')


def _write_atomic(path,data):
    if path.is_symlink():
        raise MediaError('Der Bildspeicher enthält einen unzulässigen Verweis.')
    if path.exists():
        if not path.is_file():
            raise MediaError('Der Bildspeicher ist nicht verfügbar.')
        with os.fdopen(os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)),'rb') as existing:
            if existing.read(len(data)+1)==data:
                return
    temporary = path.with_name('.'+uuid.uuid4().hex+'.tmp')
    try:
        descriptor = os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(descriptor,'wb') as output:
            output.write(data);output.flush();os.fsync(output.fileno())
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def store_image(db,uploads_dir,stream,*,mime_type=None,user_id=None):
    image = normalize_image(stream,mime_type)
    try:
        directory = media_directory(uploads_dir,image.digest,create=True)
        for name,data in image.files.items():
            _write_atomic(directory/(name+'.webp'),data)
    except OSError as error:
        raise MediaError('Das Bild konnte nicht gespeichert werden. Bitte den Speicherplatz und die Zugriffsrechte prüfen.') from error
    db.execute('''INSERT OR IGNORE INTO product_media_files(hash,width,height,size_bytes,created_by_user_id)
        VALUES (?,?,?,?,?)''',(image.digest,image.width,image.height,len(image.files['full']),user_id))
    return {'hash':image.digest,'width':image.width,'height':image.height,'size_bytes':len(image.files['full']),'mime_type':'image/webp'}
