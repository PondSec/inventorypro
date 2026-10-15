from io import BytesIO
from pathlib import Path
import struct
import zlib
import os
import pytest
from PIL import Image
import app as inventory_app
from inventorypro.domains.catalog.media import MAX_UPLOAD_BYTES, MediaError, normalize_image, store_image, media_path, open_media


def image_bytes(format='PNG',size=(120,80),exif=None):
    output = BytesIO()
    Image.new('RGB',size,(20,80,180)).save(output,format=format,**({'exif':exif} if exif else {}))
    return output.getvalue()


@pytest.mark.parametrize('format,mime',[('JPEG','image/jpeg'),('PNG','image/png'),('WEBP','image/webp')])
def test_supported_rasters_are_reencoded_and_have_bounded_variants(format,mime):
    result = normalize_image(BytesIO(image_bytes(format,size=(2000,1000))),mime)
    assert (result.width,result.height)==(1600,800)
    for variant,maximum in [('full',1600),('large',512),('thumb',96)]:
        with Image.open(BytesIO(result.files[variant])) as image:
            assert image.format=='WEBP' and max(image.size)<=maximum
            assert not image.getexif() and not image.info.get('icc_profile')


def test_exif_orientation_is_applied_and_private_metadata_is_removed():
    exif=Image.Exif();exif[274]=6;exif[315]='Sensitive owner and SERIAL-QA-SECRET'
    result=normalize_image(BytesIO(image_bytes('JPEG',size=(12,8),exif=exif)))
    assert (result.width,result.height)==(8,12)
    for data in result.files.values():
        assert b'SERIAL-QA-SECRET' not in data
        assert Image.open(BytesIO(data)).getexif()=={}


def test_storage_deduplicates_and_survives_reopen_without_original_payload(isolated_inventory,tmp_path):
    source=image_bytes()+b'<script>appended private payload</script>'
    with isolated_inventory.app_context():
        db=inventory_app.get_db()
        first=store_image(db,inventory_app.UPLOADS_DIR,BytesIO(source),mime_type='image/png')
        second=store_image(db,inventory_app.UPLOADS_DIR,BytesIO(image_bytes()),mime_type='image/png')
        db.commit()
        assert first==second and db.execute('SELECT count(*) FROM product_media_files').fetchone()[0]==1
        assert len(list(Path(inventory_app.UPLOADS_DIR).rglob('*.webp')))==3
        with open_media(inventory_app.UPLOADS_DIR,first['hash'],'full') as image:
            assert b'appended private payload' not in image.read()
        path=media_path(inventory_app.UPLOADS_DIR,first['hash'],'thumb')
        assert path.stat().st_mode & 0o777 == 0o600
    with isolated_inventory.app_context():
        assert inventory_app.get_db().execute('SELECT hash FROM product_media_files').fetchone()[0]==first['hash']


@pytest.mark.parametrize('payload,mime',[(b'<svg xmlns="http://www.w3.org/2000/svg"/>','image/svg+xml'),(b'<html>not an image</html>','image/png'),(b'','image/png'),(image_bytes(),'image/jpeg'),(b'x'*(MAX_UPLOAD_BYTES+1),'image/png')])
def test_invalid_types_mime_mismatches_and_size_limits(payload,mime):
    with pytest.raises(MediaError):normalize_image(BytesIO(payload),mime)


def test_dimension_limits_are_checked_before_decoding_large_pixel_buffers():
    def chunk(name,data):return struct.pack('!I',len(data))+name+data+struct.pack('!I',zlib.crc32(name+data)&0xffffffff)
    payload=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',6000,5000,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''))+chunk(b'IEND',b'')
    with pytest.raises(MediaError,match='24 Megapixel'):normalize_image(BytesIO(payload),'image/png')
    with pytest.raises(MediaError,match='10.000 Pixel'):normalize_image(BytesIO(image_bytes(size=(10001,1))),'image/png')


def test_animated_images_are_rejected():
    output=BytesIO();Image.new('RGB',(10,10),'red').save(output,format='WEBP',save_all=True,append_images=[Image.new('RGB',(10,10),'blue')],duration=100,loop=0)
    with pytest.raises(MediaError,match='Animation'):normalize_image(BytesIO(output.getvalue()),'image/webp')


def test_hash_paths_and_symlinks_cannot_escape_image_storage(isolated_inventory,tmp_path):
    with isolated_inventory.app_context():
        media=store_image(inventory_app.get_db(),inventory_app.UPLOADS_DIR,BytesIO(image_bytes()))
    with pytest.raises(MediaError):media_path(inventory_app.UPLOADS_DIR,'../outside')
    with pytest.raises(MediaError):media_path(inventory_app.UPLOADS_DIR,media['hash'],'../../outside')
    target=media_path(inventory_app.UPLOADS_DIR,media['hash'],'thumb');target.unlink()
    secret=tmp_path/'private.txt';secret.write_text('private')
    target.symlink_to(secret)
    with pytest.raises(MediaError):open_media(inventory_app.UPLOADS_DIR,media['hash'],'thumb')
    with isolated_inventory.app_context(),pytest.raises(MediaError):
        store_image(inventory_app.get_db(),inventory_app.UPLOADS_DIR,BytesIO(image_bytes()))
    target.unlink();os.mkfifo(target)
    with pytest.raises(MediaError):open_media(inventory_app.UPLOADS_DIR,media['hash'],'thumb')
