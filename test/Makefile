# makefile for testing module
# SOURCEDIR is set in top makefile
CURDIR		:=$(shell pwd)
OUTPUTDIR	:=$(CURDIR)/outputs

.PHONY: test pdf2docx docx2pdf check clean


test: pdf2docx docx2pdf check


pdf2docx: 
	@pytest -v test.py::TestConversion --cov="$(SOURCEDIR)" --cov-report=xml


docx2pdf:
	@if [ -n "$(wildcard outputs/*.docx)" ] ; then \
		echo "Converting docx to pdf for comparing..." ; \
		cd $(OUTPUTDIR) && for f in *.docx ; do OfficeToPDF $$f ; done ; \
	fi

check:
	@pytest -v test.py::TestQuality


clean:
	@if [ -d "$(OUTPUTDIR)" ];  then rm -rf "$(OUTPUTDIR)" ; fi
	@if [ -e ".coverage" ];  then rm -f ".coverage" ; fi
	@if [ -e "coverage.xml" ];  then rm -f "coverage.xml" ; fi