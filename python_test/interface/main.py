# -*- coding: utf-8 -*-
import sys

from PyQt4 import QtGui, uic, QtCore
from mainwindow import MainWindow
import logging

if __name__ == '__main__':
    logging.basicConfig(filename='', level=logging.DEBUG)
    logging.getLogger("PyQt4").setLevel(logging.INFO)
    
    app = QtGui.QApplication(sys.argv)
    widget = MainWindow()
    widget.show()
    sys.exit(app.exec_())  