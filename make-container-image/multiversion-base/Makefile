image:
	docker build \
		--pull \
		--build-arg "http_proxy=$(http_proxy)" \
		--build-arg "https_proxy=$(https_proxy)" \
		--build-arg "MV_BASE_PACKAGES=$(MV_BASE_PACKAGES)" \
		--build-arg "MV_EXTRA_CA_CERT=$(MV_EXTRA_CA_CERT)" \
		-t multiversion-base .
