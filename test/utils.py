import os
from urllib3 import encode_multipart_formdata
import requests
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

    def get_docx_path(self, pdf_file):
        '''get docx filename based on current pdf file'''
        pdf_filename = os.path.basename(pdf_file)
        docx_filename = pdf_filename[0:-3] + 'docx' # .pdf -> .docx
        return os.path.join(self.output_dir, docx_filename)


    @staticmethod
    def docx2pdf(docx_path):
        '''convert docx file to pdf with on-line service'''

        # service host
        url = 'http://47.100.11.147:8080'

        # headers
        headers = {
            'Referer': 'http://www.pdfdi.com/word2pdf',
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:50.0) Gecko/20100101 Firefox/50.0'
            } 

        # upload docx to perform conversion
        response = upload_docx(docx_path, url, headers)
        if not response.get('success', False): return False

        # wait for generating pdf
        time.sleep(2)

        # download zip
        zip_path = docx_path[0:-4] + 'zip'
        key = response.get('file_key', '')
        download_zip(zip_path, url, key, headers)
        if not os.path.exists(zip_path): return False

        # extract pdf
        pdf_path = docx_path[0:-4] + 'pdf'
        if os.path.exists(pdf_path): os.remove(pdf_path)
        unzip_pdf(zip_path, pdf_path)
        os.remove(zip_path)

        return True


def upload_docx(file_path, url, headers):
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
    response = requests.post(
        url=f'{url}/doc/word2pdf', 
        headers=updated_headers, 
        data=data,
        timeout=5).json()

    return response


def download_zip(zip_path, url, file_key, headers):
    ''' download converted pdf file from given url:
        http://47.100.11.147:8080/download?file_key=xxx&handle_type=word2pdf
    '''
    params = {
        'file_key': file_key,
        'handle_type': 'word2pdf'
    }
    response = requests.get(f'{url}/download',
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

