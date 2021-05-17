from pdf2docx import *
from tkinter import *
from tkinter.filedialog import *
from tkinter import filedialog
import sys
import webbrowser

root = Tk()
root.title('PDF_2_Docx Converter')
root.geometry('500x700')
root.config(bg='grey')
root.iconbitmap('icon.ico')


# Opens file explorer
# and let you select choose the pdf file that you want to convert
def pdf_file_location():
    global filenames
    Tk().withdraw()
    filenames = askopenfilenames()
    file_path_pdf_entry.insert(0, filenames)


# Opens file explorer
# and let you choose the folder, that all the converted file or files going to saved.
def docx_folder_location():
    global folder_selected
    after_convert_folder = filedialog.askdirectory()
    Tk().withdraw()
    folder_selected = after_convert_folder
    file_path_docx_entry.insert(0, folder_selected)


# Starts the convert of the file or files
def convert_button_function():

    # function for pop window 1
    def close():
        root2.destroy()

    # function for pop window 2
    def close_2():
        root3.destroy()

    # function for pop window 3
    def close_3():
        root4.destroy()

    # function for pop window 4
    def close_4():
        root5.destroy()

    # function for pop window 5
    def close_5():
        root5.destroy()
        file_number = 0
        for file in filenames:
            file_number += 1
            cv = Converter(file)
            cv.convert(folder_selected + '/' + 'Docx' + str(file_number) + '.docx', start=0, end=None)
            cv.close()

    # Window pop ups #
    if len(file_path_docx_entry.get()) == 0 and len(file_path_pdf_entry.get()) == 0:
        root4 = Tk()
        root4.title('Neither files or folder selected')
        root4.geometry('400x100')
        root4.config(bg='grey')
        root4.iconbitmap('icon.ico')

        """Labels"""
        selected_folder = Label(root4, text='Select PDF file or files for convert \n'
                                            'and Select a folder for the converted files!',
                                font='Arial 15', bg='grey', border=2)
        selected_folder.grid(row=1, column=1, sticky='w', padx=15)

        """Buttons"""
        close_button_3 = Button(root4, text='Close', command=close_3)
        close_button_3.grid(column=1, row=2, sticky='n', pady=5, ipady=5, ipadx=5, padx=15)

        root4.mainloop()

    elif len(file_path_pdf_entry.get()) == 0:
        root3 = Tk()
        root3.title('Not files for convert selected')
        root3.geometry('400x80')
        root3.config(bg='grey')
        root3.iconbitmap('icon.ico')

        """Buttons"""
        close_button_2 = Button(root3, text='Close', command=close_2)
        close_button_2.grid(column=1, row=2, sticky='n', pady=5, ipady=5, ipadx=5, padx=30)

        """Labels"""
        selected_files = Label(root3, text='Select PDF file or PDF files for convert', font='Arial 15', bg='grey',
                               border=2)
        selected_files.grid(row=1, column=1, sticky='n', padx=30)

        root3.mainloop()

    elif len(file_path_docx_entry.get()) == 0:
        root2 = Tk()
        root2.title('Not files folder selected')
        root2.geometry('400x80')
        root2.config(bg='grey')
        root2.iconbitmap('icon.ico')

        """Buttons"""

        close_button = Button(root2, text='Close', command=close)
        close_button.grid(column=1, row=2, sticky='n', pady=5, ipady=5, ipadx=5)

        """Labels"""
        selected_folder = Label(root2, text='Select a folder for the converted files!', font='Arial 15', bg='grey',
                                border=2)
        selected_folder.grid(row=1, column=1, sticky='w', padx=30)

        root2.mainloop()

    else:

        root5 = Tk()
        root5.iconbitmap('icon.ico')
        root5.title('Important!')
        root5.config(bg='grey')

        """Label"""
        warning_message_label = Label(root5, text='Make sure, that you don"t have any .docx file \n '
                                                  'in the selected folder with name Docx1, 2, 3, 4..., \n '
                                                  'because, maybe it will be replaced', font='Impact 20', bg='grey')
        warning_message_label.grid(column=1, row=1)

        """Buttons"""

        close_button_4 = Button(root5, text='Continue', command=close_5, border=2, font='Arial 10')
        close_button_4.grid(column=1, row=2, sticky='se', padx=180, ipady=5, ipadx=10)

        cancel_button = Button(root5, text='Cancel', command=close_4, border=2, font='Arial 10')
        cancel_button.grid(column=1, row=2, sticky='sw', padx=180, ipady=5, ipadx=10)

        root5.mainloop()
    ##################


# Close the program window
def close_window():
    sys.exit()


# take you to a webpage, to tell you, how to check your file or files
def callback():
    webbrowser.open_new(r"https://support.policystat.com/hc/en-us/articles"
                        r"/207993346-How-can-I-tell-if-my-PDFs-are-text-based-or-not-")


"""Labels"""

program_use_label = Label(text='PDF to Docx', font='Impact 40', bg='white', fg='#1E90FF')
program_use_label.grid(column=2, row=1, sticky='n', pady=50, padx=120)

check_label = Label(text='*This converter can only convert text based pdf \n cant convert image based pdf',
                    bg='grey')
check_label.grid(row=7, column=2, pady=10)


"""Entries"""

# PDF file entry
file_path_pdf_entry = Entry(border=5)
file_path_pdf_entry.grid(ipadx=90, ipady=4, padx=20, sticky='nw', column=2, pady=1, row=2)

# Docx file entry
file_path_docx_entry = Entry(border=5)
file_path_docx_entry.grid(column=2, ipady=4, ipadx=90, padx=20, sticky='nw', pady=70, row=3)


"""Buttons"""

converter_button = Button(text='Convert', bg='#1E90FF', fg='white', font='impact 20', border=5,
                          command=convert_button_function)
converter_button.grid(padx=175, sticky='s', ipady=5, ipadx=10, column=2, row=4)

select_pdf_file = Button(text='Select PDF files', fg='black', bg='white', border=3,
                         command=pdf_file_location)
select_pdf_file.grid(column=2, sticky='ne', row=2, pady=6, padx=60)

select_new_file_folder = Button(text='Select new files folder', fg='black', bg='white', border=3,
                                command=docx_folder_location)
select_new_file_folder.grid(column=2, sticky='ne', row=3, pady=74, padx=26)

quit_button = Button(text='Quit', bg='#1E90FF', fg='white', font='impact 20', border=5, command=close_window)
quit_button.grid(row=6, column=2, pady=30, ipadx=30)

file_check_button = Button(text='how to check my file?', bg='grey', fg='black', command=callback)
file_check_button.grid(column=2)

root.mainloop()
