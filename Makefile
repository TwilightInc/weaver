# Define the prefix (default is user-local installation)
prefix ?= $(HOME)/.local

# Define installation directories based on the prefix
install_dir := $(prefix)/lib
bin_dir := $(prefix)/bin
icon_dir := $(prefix)/share/icons/hicolor/scalable/apps
desktop_dir := $(prefix)/share/applications

# Check if running as root (id -u == 0)
ifeq ($(shell id -u),0)
	prefix ?= /usr
	install_dir := $(prefix)/lib
	bin_dir := $(prefix)/bin
	icon_dir := $(prefix)/share/icons/hicolor/scalable/apps
	desktop_dir := $(prefix)/share/applications
endif

# Create necessary directories for the installation
install:
	# Create the directories for the installation
	mkdir -p $(install_dir)/weaver
	mkdir -p $(icon_dir)
	mkdir -p $(bin_dir)
	mkdir -p $(desktop_dir)

	# Copy Python files to the appropriate directory
	cp ./main.py $(install_dir)/weaver/
	cp ./adblockeryt.py $(install_dir)/weaver/

	# Copy the icon to the appropriate directory
	cp ./data/icons/hicolor/scalable/apps/org.twilight.weaver.svg $(icon_dir)/

	# Copy the desktop file to the appropriate directory
	cp ./data/applications/org.twilight.weaver.desktop $(desktop_dir)/

	# Create a symbolic link in the bin directory
	ln -sf $(install_dir)/weaver/main.py $(bin_dir)/weaver

	echo "Installation completed successfully to $(install_dir), $(bin_dir), $(icon_dir), and $(desktop_dir)."
