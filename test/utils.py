import os
import sys
from urllib3 import encode_multipart_formdata
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util import Retry
import time
import zipfile

script_path = os.path.abspath(__file__) # current script path

class Utility:
    '''utilities'''

    @property
    def test_dir(self):
        return os.path.dirname(script_path)

    @property
    def sample_dir(self):
        return os.path.join(self.test_dir, 'samples')

    @property
    def output_dir(self):
        return os.path.join(self.test_dir, 'outputs')

    @staticmethod
    def docx2pdf(docx_path, pdf_path):
        '''convert docx file to pdf with'''

        if os.path.exists(pdf_path): os.remove(pdf_path)

        # local test only with OfficeToPDF installed
        if docx2pdf_win(docx_path, pdf_path):
            return True
        # on-line conversion is used considering no app from Linux side with a 
        # good converting quality
        else:
            return docx2pdf_online(docx_path, pdf_path)


def docx2pdf_win(docx_path, pdf_path):
    '''convert docx to pdf with OfficeToPDF:
       https://github.com/cognidox/OfficeToPDF/releases
    '''
    # convert pdf with command line
    cmd = f'OfficeToPDF "{docx_path}" "{pdf_path}"'
    os.system(cmd)

    # check results    
    return os.path.exists(pdf_path)


def docx2pdf_online(docx_path, pdf_path):
    '''convert docx file to pdf with on-line service'''

    # service host
    url = 'http://47.100.11.147:8080'

    # headers
    headers = {
        'Referer': 'http://www.pdfdi.com/word2pdf',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:50.0) Gecko/20100101 Firefox/50.0'
        } 

    # requests session
    session = requests.Session()
    session.mount('http://', HTTPAdapter(
        max_retries=Retry(total=3, method_whitelist=frozenset(['GET', 'POST']))
        ))

    # upload docx to perform conversion
    response = upload_docx(session, docx_path, url, headers)
    if not response.get('success', False): return False

    # wait for generating pdf
    time.sleep(2)

    # download zip
    zip_path = docx_path[0:-4] + 'zip'
    key = response.get('file_key', '')
    download_zip(session, zip_path, url, key, headers)
    if not os.path.exists(zip_path): return False

    # extract pdf    
    unzip_pdf(zip_path, pdf_path)
    os.remove(zip_path)

    return True


def upload_docx(session, file_path, url, headers):
    ''' on-line docx conversion: http://www.pdfdi.com/word2pdf
        return response json:
        {
            'success': True, 
            'file_key': '36300b8863be8034d713df2803c2e53e', 
            'handle_type': 'word2pdf', 
            'uploadid': None
        }
    '''
    # docx file content
    with open(file_path, mode='rb') as f:
        content = f.read() 
    
    # prepare post data
    filename = os.path.basename(file_path) 
    file = {
        'file': (filename, content)
        }
    encode_data = encode_multipart_formdata(file)
    data = encode_data[0]

    # update headers
    updated_headers = {
        'Content-Type': encode_data[1]
        }
    updated_headers.update(headers)
    
    # submit    
    try:
        response = session.post(
            url=f'{url}/doc/word2pdf', 
            headers=updated_headers, 
            data=data,
            timeout=20)
    except:
        return {}
    else:
        return response.json()


def download_zip(session, zip_path, url, file_key, headers):
    ''' download converted pdf file from given url:
        http://47.100.11.147:8080/download?file_key=xxx&handle_type=word2pdf
    '''
    params = {
        'file_key': file_key,
        'handle_type': 'word2pdf'
    }

    response = session.get(f'{url}/download',
        headers=headers,
        params=params,
        timeout=5)

    # download zip file
    with open(zip_path, 'wb') as f:
        f.write(response.content)


def unzip_pdf(zip_file_path, pdf_file_path):
    '''unzip zip file'''
    # unzip and rename
    # only one pdf file exists in this case
    zip_file = zipfile.ZipFile(zip_file_path)
    path = os.path.dirname(zip_file_path)
    for name in zip_file.namelist():
        zip_file.extract(name, path)
        os.rename(os.path.join(path, name), pdf_file_path)   