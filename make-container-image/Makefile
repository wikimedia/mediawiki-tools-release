.PHONY: build-image push-last-image auto-stage setup-workdir clean-workdir build-auto-stage-image build-multiversion-base-image build-debug-image

SHELL = /bin/bash

workdir_volume = make-container-image-workdir

build-image: auto-stage build-multiversion-base-image
	./build-mv-image $(workdir_volume)

build-debug-image:
	@if [ -f last-build ]; then \
		./build-debug-image $$(cat last-build); \
	else \
		echo "Can't build debug image until regular image is built"; \
		false; \
	fi

build-and-push-image: build-image push-last-image

push-last-image:
	@echo Pushing image to registry
	time support/push-last-build

push-last-debug-image:
	@if [ -f last-debug-build ]; then \
		echo Pushing debug image to registry; \
		time sudo /usr/local/bin/docker-pusher $$(cat last-debug-build); \
	else \
		echo Nothing to push yet; \
		false; \
	fi

run-last-image:
	@if [ -f last-build ]; then \
		docker run -it --rm --entrypoint /bin/bash $$(cat last-build); \
	else \
		echo No last build; \
		false; \
	fi

on_releases_server := $(shell if hostname -f | egrep -q '^releases.*\.wmnet$$'; then echo yes; fi)

ifneq ($(PATCHES_DIR),)
patches_volume := -v $$(readlink -e $$PATCHES_DIR):/srv/patches
endif

# Do a single auto-stage run
auto-stage: build-auto-stage-image setup-workdir
	docker run --rm \
		-e http_proxy=$(http_proxy) \
		-e https_proxy=$(https_proxy) \
		-e ON_RELEASES_SERVER=$(on_releases_server) \
		-e MW_CONFIG_BRANCH=$(MW_CONFIG_BRANCH) \
		-v $(workdir_volume):/srv/mediawiki \
		$(patches_volume) \
		auto-stage

build-auto-stage-image:
	$(MAKE) -C auto-stage build

build-multiversion-base-image:
	$(MAKE) -C multiversion-base

setup-workdir:
	./setup-workdir $(workdir_volume)

clean-workdir:
	docker volume rm $(workdir_volume)

check:
	shellcheck auto-stage/auto-stage build-mv-image setup-workdir new-train-version build-debug-image support/*

purge-restricted-images:
	docker image ls --format '{{.Repository}}:{{.Tag}}' | grep docker-registry.discovery.wmnet/restricted | xargs -r docker image rm

# Remove images older than a day
purge-old-images:
	docker image ls docker-registry.discovery.wmnet/restricted/mediawiki-multiversion  | grep 'days ago' | awk '{print $$1 ":" $$2}' | xargs -r docker image rm
