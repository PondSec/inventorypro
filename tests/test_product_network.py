import socket
import pytest
from inventorypro.domains.catalog import network as net


@pytest.mark.parametrize('url',['http://commons.wikimedia.org/w/api.php','https://commons.wikimedia.org.evil.example/w/api.php','https://user:pass@commons.wikimedia.org/w/api.php',
 'https://127.0.0.1/w/api.php','https://[::1]/w/api.php','https://commons.wikimedia.org:8080/w/api.php','https://commons.wikimedia.org/w/api.php#fragment','https://commons.wikimedia.org/wiki/Test'])
def test_only_known_https_endpoints_are_accepted(url):
    with pytest.raises(net.ProviderError):net.validate_url(url,net.API_HOSTS)


@pytest.mark.parametrize('address',['127.0.0.1','10.0.0.1','192.168.1.1','169.254.169.254','::1','fe80::1','::ffff:127.0.0.1','100.64.0.1'])
def test_private_and_metadata_dns_results_are_blocked(monkeypatch,address):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *args,**kwargs:[(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,443))])
    with pytest.raises(net.ProviderError):net.public_address('commons.wikimedia.org')


class Response:
    def __init__(self,status=200,body=b'{}',**headers):self.status=status;self.body=body;self.headers={'Content-Type':'application/json',**headers}
    def getheader(self,key,default=None):return self.headers.get(key,default)
    def read1(self,count):chunk=self.body[:count];self.body=self.body[count:];return chunk


def setup(monkeypatch,responses):
    calls=[]
    monkeypatch.setattr(net,'public_address',lambda host:'208.80.154.224')
    class Connection:
        sock=None
        def __init__(self,host,address,timeout):calls.append((host,address));self.response=responses.pop(0)
        def request(self,*args,**kwargs):pass
        def getresponse(self):return self.response
        def close(self):pass
    monkeypatch.setattr(net,'PinnedHTTPSConnection',Connection);return calls


def test_dns_result_is_pinned_and_json_is_bounded(monkeypatch):
    calls=setup(monkeypatch,[Response()]);assert net.fetch_json('https://commons.wikimedia.org/w/api.php?a=1')=={}
    assert calls==[('commons.wikimedia.org','208.80.154.224')]
    setup(monkeypatch,[Response(body=b'x'*11)])
    with pytest.raises(net.ProviderError,match='groß'):net.fetch('https://commons.wikimedia.org/w/api.php',allowed=net.API_HOSTS,maximum=10,expected_json=True)


def test_redirects_cannot_escape_host_allowlist_or_switch_to_internal_service(monkeypatch):
    for target in ['http://commons.wikimedia.org/w/api.php','https://169.254.169.254/latest/meta-data','https://evil.example/a','https://upload.wikimedia.org/wikipedia/commons/a.png']:
        calls=setup(monkeypatch,[Response(302,Location=target)])
        with pytest.raises(net.ProviderError):net.fetch_json('https://commons.wikimedia.org/w/api.php')
        assert len(calls)==1
    setup(monkeypatch,[Response(302,Location='/w/api.php?one'),Response(302,Location='/w/api.php?two'),Response(302,Location='/w/api.php?three')])
    with pytest.raises(net.ProviderError,match='Weiterleitungen'):net.fetch_json('https://commons.wikimedia.org/w/api.php')


@pytest.mark.parametrize('response',[Response(**{'Content-Length':'10000000'}),Response(**{'Content-Length':'oops'}),Response(**{'Content-Encoding':'gzip'}),Response(**{'Content-Type':'text/html'}),Response(429),Response(body=b'[]')])
def test_unsafe_or_unavailable_provider_responses_fail_cleanly(monkeypatch,response):
    setup(monkeypatch,[response])
    with pytest.raises(net.ProviderError):net.fetch_json('https://commons.wikimedia.org/w/api.php')


def test_slow_download_exceeds_absolute_deadline(monkeypatch):
    setup(monkeypatch,[Response(body=b'{}')]);times=iter([0,1,21]);monkeypatch.setattr(net.time,'monotonic',lambda:next(times))
    with pytest.raises(net.ProviderError,match='Zeitüberschreitung'):net.fetch_json('https://commons.wikimedia.org/w/api.php')
