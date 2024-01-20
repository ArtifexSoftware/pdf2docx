'''Main window for ``pdf2docx`` graphic user interface.'''

import sys
from tkinter import Tk, messagebox
from .MainFrame import MainFrame


class App(Tk):
    '''Simple graphic user interface.'''
    def __init__(self, title:str='App', width:int=300, height:int=200):
        '''Top app window.'''
        super().__init__()
        self.title(title)
        self.geometry(f'{width}x{height}')
        self.resizable(0, 0) # not allowed to change size

        # layout on the root window
        self.__create_widgets()

        # Quit window
        self.protocol("WM_DELETE_WINDOW", self._on_closing)


    def __create_widgets(self):
        self.widget = MainFrame(self)
        self.widget.grid(column=0, row=0)


    def _on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.destroy()
            sys.exit(0)


if __name__ == "__main__":
    app = App(title='PDF_2_Docx Converter', width=500, height=600)
    app.mainloop()
