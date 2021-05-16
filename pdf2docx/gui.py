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
    number_of_the_file = 0
    for file in filenames:
        number_of_the_file += 1
        cv = Converter(file)
        cv.convert(folder_selected + '/' + 'Docx' + str(number_of_the_file) + '.docx', start=0, end=None)
        cv.close()


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

select_pdf_file = Button(text='Select PDF file', fg='black', bg='white', border=3,
                         command=pdf_file_location)
select_pdf_file.grid(column=2, sticky='ne', row=2, pady=6, padx=60)

select_new_file_folder = Button(text='Select new file folder', fg='black', bg='white', border=3,
                                command=docx_folder_location)
select_new_file_folder.grid(column=2, sticky='ne', row=3, pady=74, padx=26)

quit_button = Button(text='Quit', bg='#1E90FF', fg='white', font='impact 20', border=5, command=close_window)
quit_button.grid(row=6, column=2, pady=30, ipadx=30)

difference_button = Button(text='how to check my file?', bg='grey', fg='black', command=callback)
difference_button.grid(column=2)

root.mainloop()
