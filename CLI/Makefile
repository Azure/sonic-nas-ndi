SHELL = /bin/bash
###########################################################################
#
# Copyright 2019 Dell, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
###########################################################################

.ONESHELL:
.SHELLFLAGS += -e

SUBDIRS := clitree renderer klish 
export SONIC_CLI_ROOT=$(TOPDIR)/build
TGT_DIR := $(SONIC_CLI_ROOT)/target

.PHONY: clean

all:
	for dir in $(SUBDIRS); do \
    	$(MAKE) -C $$dir -f Makefile $@; \
	done

	rm -rf $(TOPDIR)/build/cli/*
	mv -f $(TGT_DIR) $(TOPDIR)/build/cli

clean:
	make --directory=klish clean
	rm -rf $(TOPDIR)/build/cli
	rm -rf $(TGT_DIR)
