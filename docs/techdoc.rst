.. include:: header.rst

Technical Documentation
===========================

PDF文件遵循一定的格式规范，`PyMuPDF <https://github.com/pymupdf/PyMuPDF>`_ 提供了便利的解析函数，
用于获取页面元素例如文本和形状及其位置。然后，基于元素间的相对位置关系解析内容，例如将“横纵线条
围绕着文本”解析为“表格”，将“文本下方的一条横线”解析为“文本下划线”。最后，借助
`python-docx <https://github.com/python-openxml/python-docx>`_ 将解析结果重建为docx格式的Word文档。


以下分篇介绍提取PDF页面数据、解析和重建docx过程中的具体细节：


- 提取文本图片和形状_
- 解析页面布局_
- 解析表格_
- 解析段落_


.. include:: footer.rst

.. _提取文本图片和形状: https://dothinking.github.io/2020-07-14-pdf2docx%E5%BC%80%E5%8F%91%E6%A6%82%E8%A6%81%EF%BC%9A%E6%8F%90%E5%8F%96%E6%96%87%E6%9C%AC%E3%80%81%E5%9B%BE%E7%89%87%E5%92%8C%E5%BD%A2%E7%8A%B6/
.. _解析页面布局: https://dothinking.github.io/2021-05-30-pdf2docx%E5%BC%80%E5%8F%91%E6%A6%82%E8%A6%81%EF%BC%9A%E8%A7%A3%E6%9E%90%E9%A1%B5%E9%9D%A2%E5%B8%83%E5%B1%80/
.. _解析表格: https://dothinking.github.io/2020-08-15-pdf2docx%E5%BC%80%E5%8F%91%E6%A6%82%E8%A6%81%EF%BC%9A%E8%A7%A3%E6%9E%90%E8%A1%A8%E6%A0%BC/
.. _解析段落: https://dothinking.github.io/2020-08-27-pdf2docx%E5%BC%80%E5%8F%91%E6%A6%82%E8%A6%81%EF%BC%9A%E8%A7%A3%E6%9E%90%E6%AE%B5%E8%90%BD/

