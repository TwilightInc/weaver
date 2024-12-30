# Define installation directories
install_dir := $(HOME)/.local/lib
bin_dir := $(HOME)/.local/bin
icon_dir := $(HOME)/.local/share/icons/hicolor/scalable/apps
desktop_dir := $(HOME)/.local/share/applications

# Check if running as root (id -u == 0)
ifeq ($(shell id -u),0)
	# If root, set installation directories to system-wide paths
	install_dir := /usr/lib
	bin_dir := /usr/bin
	icon_dir := /usr/share/icons/hicolor/scalable/apps
	desktop_dir := /usr/share/applications
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
