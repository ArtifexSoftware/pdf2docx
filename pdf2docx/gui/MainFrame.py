'''Main frame with grouped controls.'''

import os
from tkinter import Tk, Frame, Label, Entry, Button, filedialog, messagebox
import webbrowser
from pdf2docx import Converter


class MainFrame(Frame):
    def __init__(self, parent:Tk=None):
        '''Main frame with grouped controls. This should be attached to a parent ``Tk`` instance.'''
        super().__init__(parent)
        self.parent = parent
        self.config(bg='grey')
        self.grid(ipadx=100, ipady=100)
        self.setup_ui()

        # variables
        self.pdf_paths = set() # unique pdf files
        self.docx_folder = None

    
    def setup_ui(self):
        '''Layout of the user interface.'''
        # PDF to Docx Label
        self.program_use_label = Label(self, text='PDF to Docx', font='Impact 40', bg='white', fg='#1E90FF')
        self.program_use_label.grid(row=0, column=0, columnspan=2, padx=120, pady=50)

        # PDF file entry
        self.file_path_pdf_entry = Entry(self, border=5, width=55)
        self.file_path_pdf_entry.grid(row=1, column=0, sticky='w', ipady=4, padx=10)

        # Docx file entry
        self.file_path_docx_entry = Entry(self, border=5, width=55)
        self.file_path_docx_entry.grid(row=2, column=0, sticky='w', ipady=4, padx=10, pady=75)

        # Select PDF files Button
        self.select_pdf_file = Button(self, text='Select PDF files', 
            fg='black', 
            bg='white', 
            border=3,
            command=self._callback_pdf_file_location)
        self.select_pdf_file.grid(row=1, column=1, sticky='w')

        # Select new files folder Button
        self.select_new_file_folder = Button(self, text='Select new files folder', 
            fg='black', 
            bg='white', 
            border=3,
            command=self._callback_docx_folder_location)
        self.select_new_file_folder.grid(row=2, column=1, sticky='w')

        # Convert Button
        self.converter_button = Button(self, text='Convert', 
            bg='#1E90FF', 
            fg='white', 
            font='impact 20', 
            border=5,
            command=self._callback_convert)
        self.converter_button.grid(row=3, column=0, columnspan=2, ipady=5, ipadx=10)

        # *This converter can only convert text based pdf cant convert image based pdf Label
        self.check_label = Label(self, text='*This converter can only convert text based pdf \n cant convert image based pdf',
                            bg='grey')
        self.check_label.grid(row=4, column=0, columnspan=2, pady=10)

        # how to check my file Button
        self.file_check_button = Button(self, text='how to check my file?', 
            bg='grey', 
            fg='black',
            command=lambda: webbrowser.open_new(r"https://support.policystat.com/hc/en-us/articles"
                        r"/207993346-How-can-I-tell-if-my-PDFs-are-text-based-or-not-"))
        self.file_check_button.grid(row=5, column=0, columnspan=2)


    def _callback_pdf_file_location(self):
        '''Opens file explorer and let you select choose the pdf file that you want to convert.'''
        file_paths = filedialog.askopenfilenames(filetypes=[('PDF file', '*.pdf')])
        self.pdf_paths = set()
        for path in file_paths:
            self.pdf_paths.add(path)
        
        # show just names
        names = ';'.join([f'"{os.path.basename(path)}"' for path in self.pdf_paths])
        self.file_path_pdf_entry.delete(0, 'end')
        self.file_path_pdf_entry.insert(0, names)


    def _callback_docx_folder_location(self):
        '''Opens file explorer and let you choose the folder, that all the converted file or files going to saved.'''
        self.docx_folder = filedialog.askdirectory()
        self.file_path_docx_entry.delete(0, 'end')
        self.file_path_docx_entry.insert(0, self.docx_folder)
    

    def _callback_convert(self):
        '''Starts the convert of the file or files.'''
        # input check
        if not self.pdf_paths and not self.docx_folder:
            messagebox.showwarning(
                title='Neither files or folder selected', 
                message='Select PDF file or files for convert '
                        'and Select a folder for the converted files!')
            return

        if not self.pdf_paths:
            messagebox.showwarning(
                title='Not files for convert selected', 
                message='Select PDF file or PDF files for convert!')
            return

        if not self.docx_folder:
            messagebox.showwarning(
                title='Not files folder selected', 
                message='Select a folder for the converted files!')
            return

        # collect docx files to convert to
        docx_paths = []
        for pdf_path in self.pdf_paths:
            base_name = os.path.basename(pdf_path)
            name, ext = os.path.splitext(base_name)
            docx_path = os.path.join(self.docx_folder, f'{name}.docx')
            docx_paths.append(docx_path)
        
        if any([os.path.exists(path) for path in docx_paths]) and \
            not messagebox.askokcancel(title='Existed target file', 
                message='Docx files with same target name are found under selected folder. '
                        'Do you want to continue and replace them?'):
            return
        
        # now, do the converting work
        num_succ, num_fail = 0, 0
        for pdf_path, docx_path in zip(self.pdf_paths, docx_paths):
            cv = Converter(pdf_path)
            try:
                cv.convert(docx_path)
            except Exception as e:
                print(e)
                num_fail += 1
            else:
                num_succ += 1
            finally:
                cv.close()

        messagebox.showinfo(title='Convert Done!', 
            message=f'Successful ({num_succ}), Failed ({num_fail}).')