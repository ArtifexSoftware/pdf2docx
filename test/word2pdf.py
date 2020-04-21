from urllib3 import encode_multipart_formdata
import requests

def sendFile(filename, file_path):
    """
    :param filename：文件的名称
    :param file_path：文件的绝对路径
    """
    url = "https://altoconvertwordtopdf.com"

    with open(file_path, mode="rb") as f:
        content = f.read() 

    content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        
    files = {
        "file": (filename, content, content_type, {})
        }

    headers_from_data = {
        "Referer": url,
        'Content-Type': 'multipart/form-data',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:50.0) Gecko/20100101 Firefox/50.0'
        } 
    
    response = requests.post(
        url=f'{url}/upload', 
        headers=headers_from_data, 
        files=files).json()

    return response
    
        
if __name__=='__main__':
    # 上传文件
    res = sendFile('demo-text.docx', 'D:/21_GitHub/pdf2docx/test/outputs/demo-text.docx')
    print(res)



    # https://altoconvertwordtopdf.com/convert
    # post
    # token=...