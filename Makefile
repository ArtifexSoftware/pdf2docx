# Project makefile

# working directories and files
#
TOPDIR		:=$(shell pwd)
SRC			:=$(TOPDIR)/pdf2docx
BUILD		:=$(TOPDIR)/build
DOCSRC		:=$(TOPDIR)/doc
TEST		:=$(TOPDIR)/test
CLEANDIRS	:=.pytest_cache pdf2docx.egg-info dist

# pip install sphinx_rtd_theme

.PHONY: src doc test clean

src:
	@python setup.py sdist --formats=gztar,zip && \
	python setup.py bdist_wheel

doc:
	@if [ -f "$(DOCSRC)/Makefile" ] ; then \
	    ( cd "$(DOCSRC)" && make html MODULEDIR="$(SRC)" BUILDDIR="$(BUILD)" ) || exit 1 ; \
	fi

test:
	@if [ -f "$(TEST)/Makefile" ] ; then \
	    ( cd "$(TEST)" && make test SOURCEDIR="$(SRC)" ) || exit 1 ; \
	fi

clean:
	@if [ -e "$(DOCSRC)/Makefile" ] ; then \
	    ( cd "$(DOCSRC)" && make $@ BUILDDIR="$(BUILD)" ) || exit 0 ; \
	fi
	@for p in $(CLEANDIRS) ; do \
	    if [ -d "$(TOPDIR)/$$p" ];  then rm -rf "$(TOPDIR)/$$p" ; fi ; \
	done
	@if [ -d "$(BUILD)" ];  then rm -rf "$(BUILD)" ; fi
	@if [ -e "$(TEST)/Makefile" ] ; then \
	    ( cd "$(TEST)" && make $@ ) || exit 0 ; \
	fi