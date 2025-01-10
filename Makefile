# Set default prefix (local user installation)
prefix ?= $(HOME)/.local

# Installation directories
install_dir := $(DESTDIR)$(prefix)/lib
bin_dir := $(DESTDIR)$(prefix)/bin
icon_dir := $(DESTDIR)$(prefix)/share/icons/hicolor/scalable/apps
desktop_dir := $(DESTDIR)$(prefix)/share/applications

# Installation rules
install:
	# Create necessary directories
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

	# Print installation success message
	echo "Installation completed successfully to $(install_dir), $(bin_dir), $(icon_dir), and $(desktop_dir)."
