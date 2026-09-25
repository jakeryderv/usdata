The post-release walkthrough now installs with pip's HTTP cache off, so an install retry asks PyPI again instead of rereading the index page the first attempt cached before the upload; CI only.
