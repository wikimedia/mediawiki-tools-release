.PHONY: build-image build-mv-image push-last-image auto-stage setup-workdir clean-workdir \
	build-auto-stage-image build-multiversion-base-image build-debug-image build-webserver-image

SHELL = bash

# Despite this appearing to be an unconditional assignment, any value
# specified on the command line takes precedence.
workdir_volume = make-container-image-workdir

build-image: auto-stage build-mv-image

# Like build-image, but doesn't run auto-stage.  Intended to be invoked by scap.
build-mv-image: build-multiversion-base-image
	./build-mv-image $(workdir_volume)

build-debug-image:
	@if [ -f last-build ]; then \
		./build-debug-image $$(cat last-build); \
	else \
		echo "Can't build debug image until regular image is built"; \
		false; \
	fi

build-and-push-image: build-image push-last-image

# like build-and-push-image but doesn't run auto-stage.
build-and-push-mv-image: build-mv-image
	$(MAKE) push-last-image

build-and-push-debug-image: build-debug-image
	$(MAKE) push-last-debug-image

# To be invoked by scap. The debug image is built and pushed last.
build-and-push-all-images: build-and-push-mv-image build-and-push-webserver-image
	$(MAKE) build-and-push-debug-image

build-and-push-webserver-image:
	$(MAKE) -C webserver new-build-and-push-image
# end To be invoked by scap

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

auto_stage_network ?= bridge

# Do a single auto-stage run
auto-stage: build-auto-stage-image setup-workdir
	docker run --rm --init \
		-e http_proxy \
		-e https_proxy \
		-e ON_RELEASES_SERVER=$(on_releases_server) \
		-e MW_CONFIG_BRANCH \
		-e GIT_BASE \
		-e AUTO_STAGE_LANG \
		-e MEDIAWIKI_CONFIG_COMMIT \
		-e MEDIAWIKI_COMMITS \
		--network $(auto_stage_network) \
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
	shellcheck auto-stage/auto-stage build-mv-image setup-workdir build-debug-image support/{extract-image-tag,new-train-version,push-last-build,utils.sh} webserver/{build-webserver-image,stage-srv-mediawiki}

purge-restricted-images:
	docker image ls --format '{{.Repository}}:{{.Tag}}' | grep restricted/mediawiki | xargs -r docker image rm

# Remove images older than a day
purge-old-images:
	docker image ls docker-registry.discovery.wmnet/restricted/mediawiki-multiversion  | grep 'days ago' | awk '{print $$1 ":" $$2}' | xargs -r docker image rm
