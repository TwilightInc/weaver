install:
	# Check if the script is being run as root
	@if [ $(id -u) -eq 0 ]; then \
		install_dir="/usr/lib"; \
		bin_dir="/usr/bin"; \
		icon_dir="/usr/share/icons/hicolor/scalable/apps"; \
		desktop_dir="/usr/share/applications"; \
		echo "Running as root. Installing to $$install_dir and $$icon_dir."; \
	else \
		install_dir="~/.local/lib"; \
		bin_dir="~/.local/bin"; \
		icon_dir="~/.local/share/icons/hicolor/scalable/apps"; \
		desktop_dir="~/.local/share/applications"; \
		echo "Not running as root. Installing to $$install_dir and $$icon_dir."; \
	fi

	# Create necessary directories for the installation
	mkdir -p $$install_dir/weaver
	mkdir -p $$icon_dir
	mkdir -p $$bin_dir
	mkdir -p $$desktop_dir

	# Copy Python files to the appropriate directory
	cp ./main.py $$install_dir/weaver/
	cp ./adblockeryt.py $$install_dir/weaver/

	# Copy the icon to the appropriate directory
	cp ./data/icons/hicolor/scalable/apps/org.twilight.weaver.svg $$icon_dir/

	# Copy the desktop file to the appropriate directory
	cp ./data/applications/org.twilight.weaver.desktop $$desktop_dir/

	# Link the main endpoint to the bin directory
	ln -sf $$install_dir/main.py $$bin_dir/weaver

	echo "Installation completed successfully to $$install_dir and $$icon_dir."