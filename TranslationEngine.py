import urllib.request
import urllib.parse
import socket
import json
import re
import execjs  # pip install PyExecJS


def google_translate(source, to_lan='zh-CN', from_lan='en'):
    if len(source) > 4891:
        raise Exception('input characters out of limitation')

    # calculate tk value with javascript
    content = source.replace('\n',' ')
    js = Py4Js()
    tk = js.getTk(content)

    # request url and parameters
    url = 'http://translate.google.cn/translate_a/single?'
    data = {
        'q': content,
        'tk': tk,
        'sl': from_lan,
        'tl': to_lan,
        'client': 'webapp',
        'dt': 'at',
        'dt': 'bd',
        'dt': 'ex',
        'dt': 'ld',
        'dt': 'md',
        'dt': 'qca',
        'dt': 'rw',
        'dt': 'rm',
        'dt': 'ss',
        'dt': 't',
        'ie': 'UTF-8',
        'oe': 'UTF-8'        
    }

    # check results
    page = urllib_request(url, data)
    res_json = json.loads(page)
    res = ''.join(item[0] for item in res_json[0] if item) if res_json[0] else None
    return res

def google_translate1(source, to_lan='zh', from_lan='en'):
    # request url and parameters
    url = 'https://translate.google.cn/m?'
    data = {
        'sl': from_lan,
        'hl': to_lan,
        'q': source.replace('\n', ' ')
    }    

    # check results
    # <div dir="ltr" class="t0">...</div>
    page = urllib_request(url, data)
    pattern = '<div dir="ltr" class="t0">(.+?)</div>'
    res_found = re.findall(pattern, page)
    res = res_found[0] if res_found else None
    return res

def youdao_translate(source, to_lan='zh', from_lan='en'):
    # request url and parameters
    url = "http://fanyi.youdao.com/translate?"
    data = {
        "i": source.replace('\n', ' '),
        "from": from_lan,
        "to": to_lan,
        "smartresult": "dict",
        "doctype": "json",
        "version": "2.1",
        "keyfrom": "fanyi.web",
        "action": "FY_BY_REALTIME",
        "typoResult": "true"
    }

    # check results
    page = urllib_request(url, data, 'post')
    res_json = json.loads(page)
    if res_json['errorCode'] == 0:
        res = ''.join([item['tgt'] for item in res_json['translateResult'][0]])
    else:
        res = None
    return res

def bing_translate(source, to_lan='zh-CHS', from_lan='en'):
    if len(source) > 4891:
        raise Exception('input characters out of limitation')

    # request url and parameters
    url = 'https://cn.bing.com/ttranslate?&IG=C4A52C35D175427988E6510779DEFB5F&IID=translator.5036.8'
    data = {
        'text': source.replace('\n',' '),
        'from': from_lan,
        'to': to_lan,
        'doctype': 'json'
    }

    # check results
    page = urllib_request(url, data, 'post')
    res_json = json.loads(page)
    res = res_json['translationResponse'] if res_json['statusCode'] == 200 else None
    return res

class Py4Js():

    def __init__(self):
        self.ctx = execjs.compile('''
            function TL(a) { 
                var k = ""; 
                var b = 406644; 
                var b1 = 3293161072; 
                var jd = "."; 
                var $b = "+-a^+6"; 
                var Zb = "+-3^+b+-f"; 
                for (var e = [], f = 0, g = 0; g < a.length; g++) { 
                    var m = a.charCodeAt(g); 
                    128 > m ? e[f++] = m : (2048 > m ? e[f++] = m >> 6 | 192 : (55296 == (m & 64512) && g + 1 < a.length && 56320 == (a.charCodeAt(g + 1) & 64512) ? (m = 65536 + ((m & 1023) << 10) + (a.charCodeAt(++g) & 1023), 
                    e[f++] = m >> 18 | 240, 
                    e[f++] = m >> 12 & 63 | 128) : e[f++] = m >> 12 | 224, 
                    e[f++] = m >> 6 & 63 | 128), 
                    e[f++] = m & 63 | 128) 
                } 
                a = b; 
                for (f = 0; f < e.length; f++) a += e[f], 
                a = RL(a, $b); 
                a = RL(a, Zb); 
                a ^= b1 || 0; 
                0 > a && (a = (a & 2147483647) + 2147483648); 
                a %= 1E6; 
                return a.toString() + jd + (a ^ b) 
            }; 
            function RL(a, b) { 
                var t = "a"; 
                var Yb = "+"; 
                for (var c = 0; c < b.length - 2; c += 3) { 
                    var d = b.charAt(c + 2), 
                    d = d >= t ? d.charCodeAt(0) - 87 : Number(d), 
                    d = b.charAt(c + 1) == Yb ? a >>> d: a << d; 
                    a = b.charAt(c) == Yb ? a + d & 4294967295 : a ^ d 
                } 
                return a 
            } 
        ''')

    def getTk(self, text):
        return self.ctx.call("TL", text)

def urllib_request(url, data, method='get', timeout=10, proxy={}):
    # requesting data
    request_headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.108 Safari/537.36',
    }
    data = urllib.parse.urlencode(data)

    # send request: get/post
    if method=='get':
        request = urllib.request.Request(url+data, headers=request_headers)
    else:
        request = urllib.request.Request(url, data=data.encode(), headers=request_headers)

    # proxy
    proxy_support = urllib.request.ProxyHandler(proxy)
    opener = urllib.request.build_opener(proxy_support)
    urllib.request.install_opener(opener)

    # timeout
    # socket.setdefaulttimeout(timeout)
    
    # response
    response = urllib.request.urlopen(request)
    res = response.read().decode('utf-8')

    return res

if __name__ == '__main__':
    
    src = '''This book is targeted primarily toward engineers and engineering students of advanced standing (sophomores, seniors and graduate students). Familiar ity with a
        computer language is required; knowledge of basic engineer ing mechanics is useful,
        but not essential.
        The text attempts to place emphasis on numer ical methods, not programming.
        Most engineers are not programmers, but problem solvers. They want to know what
        methods can be applied to a given problem, what are their strengths and pitfalls and
        how to implement them. Engineers are not expected to wr ite computer code for basic
        tasks from scratch; they are more likely to utilize functions and subroutines that have
        been already wr itten and tested. Thus programming by engineers is largely confined
        to assembling existing pieces of code into a coherent package that solves the problem
        at hand.
        The “piece” of code is usually a function that implements a specific task. For the
        user the details of the code are unimpor tant. What matters is the inter face (what goes
        in and what comes out) and an understanding of the method on which the algor ithm
        is based. Since no numer ical algor ithm is infallible, the impor tance of understanding
        the underlying method cannot be overemphasized; it is, in fact, the rationale behind
        lear ning numer ical methods.
        This book attempts to confor m to the views outlined above. Each numer ical
        method is explained in detail and its shor tcomings are pointed out. The examples that
        follow individual topics fall into two categor ies: hand computations that illustrate the
        inner workings of the method and small programs that show how the computer code is
        utilized in solving a problem. Problems that require programming are marked with  .
        The mater ial consists of the usual topics covered in an engineer ing course on
        numer ical methods: solution of equations, interpolation and data fitting, numer ical
        differentiation and integration, solution of ordinar y differential equations and eigenvalue problems. The choice of methods within each topic is tilted toward relevance
        to engineer ing problems. For example, there is an extensive discussion of symmetric, sparsely populated coefficient matr ices in the solution of simultaneous equations.
        In the same vein, the solution of eigenvalue problems concentrates on methods that
        efficiently extract specific eigenvalues from banded matr ices.'''


    # print('Google translate:')
    # print(google_translate(src))
    print('google translate 1:')
    print(google_translate1(src))
    # print('Youdao translate:')
    # print(youdao_translate(src))
    # print('Bing translate:')
    # print(bing_translate(src))