import os

script_path = os.path.abspath(__file__) # current script path

PUB_KEY = 'project_public_01b82150d1672bd1356f4806844a051d_XTDB4bb0d513117368a337eda0f723f4efdc3'


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

    def docx2pdf(self, docx_path, pdf_path):
        '''convert docx file to pdf with'''

        if os.path.exists(pdf_path): os.remove(pdf_path)

        # local test only with OfficeToPDF installed
        if self._docx2pdf_win(docx_path, pdf_path):
            return True
        # on-line conversion is used considering no app from Linux side with a 
        # good converting quality
        else:
            return self._docx2pdf_online(docx_path, pdf_path)

    @staticmethod
    def _docx2pdf_online(docx_path, pdf_path):
        ''' convert office file to pdf with ILOVEPDF python api:    
            https://github.com/AndyCyberSec/pylovepdf
        '''
        from pylovepdf.tools.officepdf import OfficeToPdf

        out_dir = os.path.dirname(pdf_path)
        t = OfficeToPdf(PUB_KEY, verify_ssl=True, proxies=None)
        t.add_file(docx_path)
        t.set_output_folder(out_dir)
        t.execute()
        converted_pdf_name = t.download() # return pdf filename
        t.delete_current_task()

        # rename pdf if successes
        if converted_pdf_name==None:
            return False
        else:
            converted_pdf_path = os.path.join(out_dir, converted_pdf_name)
            os.rename(converted_pdf_path, pdf_path)
            return True

    @staticmethod
    def _docx2pdf_win(docx_path, pdf_path):
        '''convert docx to pdf with OfficeToPDF:
        https://github.com/cognidox/OfficeToPDF/releases
        '''
        # convert pdf with command line
        cmd = f'OfficeToPDF "{docx_path}" "{pdf_path}"'
        os.system(cmd)

        # check results    
        return os.path.exists(pdf_path)