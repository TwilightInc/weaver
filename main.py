#!/usr/bin/env python3
## Weaver [Version 1.0]
## (c) Twilight Incorporated. All rights reserved.

import gi
import sys
import re
import requests
import sqlite3
import random
import string
import os
from io import BytesIO
from datetime import datetime
gi.require_version('Gtk', '4.0')
gi.require_version('WebKit', '6.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, WebKit, Gio, GLib, Gdk, GdkPixbuf
from PIL import Image  # Import the Pillow library for image conversion
import configparser
import hashlib

# Helper function to generate profile name
def generate_profile_name():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

# Helper function to create or read config.ini for the default profile
def read_or_create_config():
    config_path = os.path.expanduser("~/.weaver/config.ini")
    config = configparser.ConfigParser()

    if os.path.exists(config_path):
        # If config.ini exists, read it
        config.read(config_path)
        profile_name = config.get("Settings", "profile_name", fallback=None)
    else:
        # If config.ini doesn't exist, create it and set default profile
        profile_name = generate_profile_name()
        config["Settings"] = {"profile_name": profile_name}
        with open(config_path, "w") as config_file:
            config.write(config_file)

    return profile_name

class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hb = Adw.HeaderBar()
        self.set_titlebar(self.hb)
        self.app_name = app_name
        self.html = '''<h1>W.I.P.</h1><p>This page would be replaced soon</p><hr/><em>Weaver</em>'''

        # Create a Box for layout
        self.a = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Create TabView and TabBar
        self.tab_view = Adw.TabView(vexpand=True)
        self.tab_bar = Adw.TabBar()
        self.tab_bar.set_view(self.tab_view)
        self.a.append(self.tab_bar)  # Add TabBar to the layout
        self.a.append(self.tab_view)  # Add TabView to the layout

        # Create the first WebView in a tab
        self.create_new_tab()

        # Create HeaderBar buttons (Back, Forward, Reload, New Tab) and set URL Entry
        self.create_headerbar_buttons()

        # Add Application Menu Button
        self.add_application_menu()

        # Create an Entry widget for the URL bar
        self.url_entry = Gtk.Entry()
        self.url_entry.set_text("")  # Set default URL
        self.url_entry.set_placeholder_text("Enter a URL or search...")  # Set placeholder text
        self.url_entry.set_width_chars(80)  # Increase width of the URL Entry
        self.url_entry.connect("changed", self.on_url_changed)  # Connect signal when text changes
        self.url_entry.connect("activate", self.on_url_activated)  # Connect signal when Enter is pressed

        # Set the Entry widget as the title widget in the HeaderBar
        self.hb.set_title_widget(self.url_entry)

        # Add the layout (Box) to the window
        self.set_child(self.a)

        # Apply CSS styling for transparent buttons on the left
        self.apply_button_style()

        # Connect to the "notify::selected-page" signal to update the URL bar when the tab changes
        self.tab_view.connect("notify::selected-page", self.on_tab_changed)

        # Track whether the grid view is active
        self.is_grid_view_active = False

        # Connect navigation signals when the tab or WebView changes
        self.connect_navigation_signals()

        # Initial update of button state
        self.update_navigation_buttons(self.get_current_webview())

        # Read or create config.ini to get the profile name
        self.profile_name = read_or_create_config()

        # Create the directory for the profile
        self.profile_directory = os.path.expanduser(f"~/.weaver/{self.profile_name}.default")
        os.makedirs(self.profile_directory, exist_ok=True)
        
        # Initialize the databases directly here
        self.history_db = self.initialize_history_db()
        self.bookmarks_db = self.initialize_bookmarks_db()
        
        self.create_bookmarks_menu()
        
        # Connect the icon-press signal
        self.url_entry.connect("icon-press", self.on_icon_pressed)

    def initialize_history_db(self):
        self.profile_name = read_or_create_config()
        self.profile_directory = os.path.expanduser(f"~/.weaver/{self.profile_name}.default")
        os.makedirs(self.profile_directory, exist_ok=True)
        db_path = os.path.join(self.profile_directory, "history.db")
        # Create the database file if it doesn't exist
        if not os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                );
                ''')
                conn.commit()
        return db_path

    def initialize_bookmarks_db(self):
        self.profile_name = read_or_create_config()
        self.profile_directory = os.path.expanduser(f"~/.weaver/{self.profile_name}.default")
        os.makedirs(self.profile_directory, exist_ok=True)
        db_path = os.path.join(self.profile_directory, "bookmarks.db")
        # Create the database file if it doesn't exist
        if not os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL
                );
                ''')
                conn.commit()
        return db_path

    def add_to_history(self, url, title):
        self.history_db = self.initialize_history_db()
        self.bookmarks_db = self.initialize_bookmarks_db()
        # Insert a new record for visited URL
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.history_db) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO history (url, title, timestamp) VALUES (?, ?, ?)", (url, title, timestamp))
            conn.commit()

    def get_history(self):
        self.history_db = self.initialize_history_db()
        self.bookmarks_db = self.initialize_bookmarks_db()
        # Get all history records, ordered by most recent
        with sqlite3.connect(self.history_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT url, title, timestamp FROM history ORDER BY timestamp DESC")
            return cursor.fetchall()
            
    def delete_from_history(self, url, title, timestamp):
        self.history_db = self.initialize_history_db()
        self.bookmarks_db = self.initialize_bookmarks_db()
        with sqlite3.connect(self.history_db) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history WHERE url = ? AND title = ? AND timestamp = ?", (url, title, timestamp))
            conn.commit()

    def add_bookmark(self, url, title):
        # Insert a new bookmark
        with sqlite3.connect(self.bookmarks_db) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO bookmarks (url, title) VALUES (?, ?)", (url, title))
            conn.commit()

    def get_bookmarks(self):
        # Get all bookmarks
        with sqlite3.connect(self.bookmarks_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT url, title FROM bookmarks")
            return cursor.fetchall()

    def delete_bookmark(self, url):
        # Delete a bookmark
        with sqlite3.connect(self.bookmarks_db) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bookmarks WHERE url = ?", (url,))
            conn.commit()
            
    def remove_history_items(self):
        # Get history from the database
        history_entries = self.get_history()
        
        # Add history items to the submenu
        for url, title, timestamp in history_entries:
            self.delete_from_history(url, title, timestamp)
            self.populate_history_submenu(self.history_submenu)
        
    def populate_history_submenu(self, history_submenu):
        # Clear the current history submenu
        history_submenu.remove_all()

        # Get history from the database
        history_entries = self.get_history()

        options = Gio.Menu()
        history_items = Gio.Menu()

        options.append("Delete history items", "app.remove_history_items")

        # Add history items to the submenu
        for url, title, timestamp in history_entries:
            # Create a Gio.MenuItem for each history entry
            menu_item = Gio.MenuItem.new(f"{title}", f"app.history.{hashlib.md5(url.encode()).hexdigest()}")
            history_items.append_item(menu_item)
            
        history_submenu.append_section(None, options)
        history_submenu.append_section("Recent history", history_items)
            
    # Method to handle history item selection
    def on_history_item_selected(self, menu_item, url):
        # Handle history item selection and load the URL
        current_tab = self.tab_view.get_selected_page()
        webview = current_tab.get_child()
        if isinstance(webview, WebKit.WebView):
            webview.load_uri(url)

    # Modify the create_bookmarks_menu method to use Gio.Menu and Gtk.MenuButton
    def create_bookmarks_menu(self):
        # Create the MenuButton for bookmarks
        self.bookmarks_button = Gtk.MenuButton()
        self.bookmarks_button.set_icon_name("user-bookmarks-symbolic")

        # Create a Gio.Menu to hold the bookmarks items
        self.bookmarks_menu = Gio.Menu()

        # Populate the menu with bookmark items
        self.populate_bookmarks_menu()

        # Set the Gio.Menu for the MenuButton
        self.bookmarks_button.set_menu_model(self.bookmarks_menu)

        # Add Bookmarks button to HeaderBar
        self.hb.pack_end(self.bookmarks_button)

    def populate_bookmarks_menu(self):
        # Clear current menu items
        self.bookmarks_menu.remove_all()

        # Get bookmarks from the database
        bookmarks = self.get_bookmarks()

        # Add bookmarks to the menu
        for url, title in bookmarks:
            # Create a Gio.MenuItem for each bookmark
            menu_item = Gio.MenuItem.new(title, f"app.bookmark.{hashlib.md5(url.encode()).hexdigest()}")
            self.bookmarks_menu.append_item(menu_item)

    def on_bookmark_selected(self, menu_item, url):
        # Handle bookmark selection and load the URL
        current_tab = self.tab_view.get_selected_page()
        webview = current_tab.get_child()
        if isinstance(webview, WebKit.WebView):
            webview.load_uri(url)

    def populate_bookmarks_list(self):
        self.bookmarks_listbox.foreach(self.bookmarks_listbox.remove)  # Clear current list
        bookmarks = self.get_bookmarks()
        for url, title in bookmarks:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=f"{title} - {url}")
            row.add(label)
            self.bookmarks_listbox.add(row)
        self.bookmarks_listbox.show_all()

    def on_bookmarks_button_clicked(self, button):
        self.popover.show_all()

    def on_url_changed(self, entry):
        # Handle URL changes here
        pass

    def on_url_activated(self, entry):
        url = entry.get_text()
        if not re.search(r'.*\.[a-z]{2,6}$.*', url):
            url = f"https://www.duckduckgo.com/?q={url}"
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "http://" + url

        current_tab = self.tab_view.get_selected_page()
        webview = current_tab.get_child()
        if isinstance(webview, WebKit.WebView):
            webview.load_uri(url)

        # Update navigation buttons after URL change
        self.update_navigation_buttons(webview)
        
    def create_headerbar_buttons(self):
        # Back Button with symbolic icon
        self.back_button = Gtk.Button()
        back_icon = Gtk.Image.new_from_icon_name("go-previous-symbolic")
        self.back_button.set_child(back_icon)
        self.back_button.connect("clicked", self.on_back_clicked)
        self.back_button.get_style_context().add_class("left-header-button")
        self.hb.pack_start(self.back_button)

        # Forward Button with symbolic icon
        self.forward_button = Gtk.Button()
        forward_icon = Gtk.Image.new_from_icon_name("go-next-symbolic")
        self.forward_button.set_child(forward_icon)
        self.forward_button.connect("clicked", self.on_forward_clicked)
        self.forward_button.get_style_context().add_class("left-header-button")
        self.hb.pack_start(self.forward_button)

        # Reload Button with symbolic icon
        reload_button = Gtk.Button()
        self.reload_icon = Gtk.Image.new_from_icon_name("view-refresh-symbolic")
        reload_button.set_child(self.reload_icon)
        reload_button.connect("clicked", self.on_reload_clicked)
        reload_button.get_style_context().add_class("left-header-button")
        self.hb.pack_start(reload_button)

        # New Tab Button with symbolic icon
        new_tab_button = Gtk.Button()
        new_tab_icon = Gtk.Image.new_from_icon_name("tab-new-symbolic")
        new_tab_button.set_child(new_tab_icon)
        new_tab_button.connect("clicked", self.on_new_tab_clicked)
        new_tab_button.get_style_context().add_class("left-header-button")
        self.hb.pack_start(new_tab_button)
    
        
    def on_back_clicked(self, button):
        current_tab = self.tab_view.get_selected_page()
        webview = current_tab.get_child()
        if isinstance(webview, WebKit.WebView) and webview.can_go_back():
            webview.go_back()

    def on_forward_clicked(self, button):
        current_tab = self.tab_view.get_selected_page()
        webview = current_tab.get_child()
        if isinstance(webview, WebKit.WebView) and webview.can_go_forward():
            webview.go_forward()

    def on_reload_clicked(self, button):
        current_tab = self.tab_view.get_selected_page()
        webview = current_tab.get_child()
        if isinstance(webview, WebKit.WebView):
            self.reload_icon.set_from_icon_name("process-stop")
            webview.reload()
    
    def connect_navigation_signals(self):
        # Connect the history change signals for the current WebView
        current_webview = self.get_current_webview()
        if current_webview:
            current_webview.connect("notify::can-go-back", lambda w, _: self.update_navigation_buttons())
            current_webview.connect("notify::can-go-forward", lambda w, _: self.update_navigation_buttons())
    
    def on_tab_changed(self, tab_view, pspec):
        selected_tab = tab_view.get_selected_page()
        webview = selected_tab.get_child()
        if isinstance(webview, WebKit.WebView):
            current_url = webview.get_uri()
            self.url_entry.set_text(current_url)

            # Update navigation buttons based on the new active tab's WebView
            self.update_navigation_buttons(webview)
    
    def get_current_webview(self):
        # Get the currently selected tab from the TabView
        selected_tab = self.tab_view.get_selected_page()
        
        # Check if the selected tab has a child (WebView)
        if selected_tab:
            webview = selected_tab.get_child()
            if isinstance(webview, WebKit.WebView):
                return webview
        
        return None  # Return None if no WebView is found
    
    def apply_button_style(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        .left-header-button {
            background-color: transparent;
            border: none;
        }
        .left-header-button:hover {
            background-color: rgba(255, 255, 255, 0.1);
        }
        """)

        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
     

    def get_favicon_from_html(self, html_content, base_url):
        # Regular expression to match the <link rel="icon" href="..."> tag
        favicon_regex = r'<link rel=["\"]icon["\"]\s+href=["\"](.*?)["\"]'
        match = re.search(favicon_regex, html_content, re.IGNORECASE)
        
        if match:
            favicon_url = match.group(1)
            # If the URL is relative, prepend the base URL
            if not favicon_url.startswith(('http://', 'https://')):
                favicon_url = f"{base_url}/{favicon_url.lstrip('/')}"
            return favicon_url
        return None

    def set_favicon_for_tab(self, tab_page, url):
        base_url = self.get_base_url(url)
        favicon_url = f"{base_url}/favicon.ico"  # Default path for favicon.ico

        try:
            # Try fetching the favicon.ico file first
            response = requests.get(favicon_url)
            response.raise_for_status()  # Raise an exception for bad responses

            # Convert the favicon to PNG using Pillow
            image = Image.open(BytesIO(response.content))
            with BytesIO() as png_image:
                image.save(png_image, format="PNG")
                png_image.seek(0)  # Go back to the start of the BytesIO buffer

                # Create a Pixbuf from the PNG image data
                pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(
                    Gio.MemoryInputStream.new_from_data(png_image.read()),
                    32, 32, True
                )

            # Set the favicon image to the tab's icon
            tab_page = self.tab_view.get_selected_page()
            tab_page.set_icon(pixbuf)

        except requests.exceptions.RequestException as e:
            # Fallback to PNG if the .ico file fails
            fallback_url = favicon_url.replace('.ico', '.png')
            try:
                response = requests.get(fallback_url)
                response.raise_for_status()  # Raise an exception for bad responses

                with BytesIO() as png_image:
                    png_image.write(response.content)
                    png_image.seek(0)  # Go back to the start of the BytesIO buffer

                    # Create a Pixbuf from the PNG image data
                    pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(
                        Gio.MemoryInputStream.new_from_data(png_image.read()),
                        32, 32, True
                    )

                # Set the favicon image to the tab's icon
                tab_page = self.tab_view.get_selected_page()
                tab_page.set_icon(pixbuf)

            except requests.exceptions.RequestException as e:
                # If both .ico and .png fail, try parsing the HTML for <link rel="icon">
                try:
                    response = requests.get(url)
                    response.raise_for_status()  # Check if the request was successful

                    # Try to extract favicon from HTML content
                    favicon_url = self.get_favicon_from_html(response.text, base_url)

                    if favicon_url:
                        # Fetch the favicon from the parsed URL (either absolute or relative)
                        response = requests.get(favicon_url)
                        response.raise_for_status()

                        # Convert the favicon to PNG using Pillow
                        image = Image.open(BytesIO(response.content))
                        with BytesIO() as png_image:
                            image.save(png_image, format="PNG")
                            png_image.seek(0)  # Go back to the start of the BytesIO buffer

                            # Create a Pixbuf from the PNG image data
                            pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(
                                Gio.MemoryInputStream.new_from_data(png_image.read()),
                                32, 32, True
                            )

                        # Set the favicon image to the tab's icon
                        tab_page = self.tab_view.get_selected_page()
                        tab_page.set_icon(pixbuf)

                    else:
                        print("No favicon found in the HTML.")
                        return None  # No favicon was found

                except requests.exceptions.RequestException as e:
                    print(f"Failed to fetch favicon using all methods: {e}")
                    return None  # Return None if all attempts fail
     
    def on_webview_load_changed(self, webview, load_event):
        if load_event == WebKit.LoadEvent.STARTED:
            self.reload_icon.set_from_icon_name("process-stop")
            selected_tab = self.tab_view.get_selected_page()
            selected_tab.set_loading(True)
        elif load_event == WebKit.LoadEvent.FINISHED:
            selected_tab = self.tab_view.get_selected_page()
            selected_tab.set_loading(False)
            current_url = webview.get_uri()

            if current_url != f'data:text/html,{self.html}':
                self.url_entry.set_text(current_url)

                if current_url.startswith("https://"):
                    # Set lock icon for the URL entry
                    self.url_entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "system-lock-screen")

                # Fetch the HTML page to update the title
                response = requests.get(current_url)
                html = response.text
                self.update_title_from_html(html)
                    
                if current_url.startswith("http://") or current_url.startswith("https://"):
                    self.current_url_to_bookmark = current_url
                    self.update_icon(current_url)
                    
                # Save to history
                self.add_to_history(current_url, self.get_title_from_url(current_url))
                
                # Add bookmark functionality
                self.populate_history_submenu(self.history_submenu)

            self.reload_icon.set_from_icon_name("view-refresh-symbolic")
            self.update_navigation_buttons(webview)

    def get_base_url(self, url):
        # Extract the base URL (protocol + domain) from the full URL
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        return base_url

    def update_icon(self, url):
        # Update the icon based on the bookmark state
        icon_name = "starred-symbolic" if url in self.get_bookmarks() else "non-starred-symbolic"
        self.url_entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, icon_name)
        selected_tab = self.tab_view.get_selected_page()
        self.set_favicon_for_tab(selected_tab, url)
        
    def on_icon_pressed(self, entry, icon_pos):
        # Toggle the bookmark state when the secondary icon is pressed
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            # Create the popout dialog
            dialog = Gtk.Dialog()
            dialog.set_modal(True)
            dialog.set_transient_for(self)
            dialog.set_title("Add Bookmark")

            # Create name and URL inputs
            content_area = dialog.get_content_area()
            grid = Gtk.Grid(column_spacing=10, row_spacing=10, margin_top=10, margin_bottom=10, margin_start=10, margin_end=10)
            content_area.append(grid)

            name_label = Gtk.Label(label="Name:")
            name_entry = Gtk.Entry()
            url_label = Gtk.Label(label="URL:")
            url_entry = Gtk.Entry()
            url_entry.set_text(self.current_url_to_bookmark)

            grid.attach(name_label, 0, 0, 1, 1)
            grid.attach(name_entry, 1, 0, 1, 1)
            grid.attach(url_label, 0, 1, 1, 1)
            grid.attach(url_entry, 1, 1, 1, 1)

            # Add buttons for the dialog
            dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)
            dialog.show()

            # Handle dialog response
            dialog.connect("response", self.on_dialog_response, name_entry, url_entry)
          
    def on_dialog_response(self, dialog, response, name_entry, url_entry):
        if response == Gtk.ResponseType.OK:
            name = name_entry.get_text()
            url = url_entry.get_text()
            self.add_bookmark(name, url)
            self.populate_bookmarks_menu()
        dialog.close()
          
    def update_navigation_buttons(self, webview):
        if webview:
            self.back_button.set_sensitive(webview.can_go_back())
            self.forward_button.set_sensitive(webview.can_go_forward())

    def update_title_from_html(self, html):
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1)
            self.update_tab_title(title)
            
    def get_title_from_url(self, url):
        response = requests.get(url)
        html = response.text
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1)
            return title

    def update_tab_title(self, title):
        selected_tab = self.tab_view.get_selected_page()
        selected_tab.set_title(title)

    def add_application_menu(self):
        # Create an Overflow Button for the application menu
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")

        self.history_submenu = Gio.Menu()
        self.populate_history_submenu(self.history_submenu)

        # Create a Menu Model for the menu items
        menu = Gio.Menu()
        menu.append("New tab", "app.new_tab")  # Menu item "New Tab"
        menu.append_submenu("History", self.history_submenu)
        menu.append(f"About {self.app_name}", "app.about")  # Menu item "About"

        # Set the menu to the button
        menu_button.set_menu_model(menu)
        self.hb.pack_end(menu_button)

    def create_new_tab(self, url=None):
        webview = WebKit.WebView()
        webview.load_uri(f'data:text/html,{self.html}')
        title = "New tab"
        tab = self.tab_view.append(webview)
        tab.set_title(title)
        self.tab_view.set_selected_page(tab)
        webview.connect("load-changed", self.on_webview_load_changed)

    def on_new_tab_clicked(self, button):
        self.create_new_tab()


# Main application class
class MyApp(Adw.Application):
    def __init__(self, version, app_name, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)
        
        action1 = Gio.SimpleAction.new("about", None)
        action1.connect("activate", self.show_about_dialog)
        self.add_action(action1)
        
        action2 = Gio.SimpleAction.new("new_tab", None)
        action2.connect("activate", self.create_new_tab)
        self.add_action(action2)
        
        action3 = Gio.SimpleAction.new("remove_history_items", None)
        action3.connect("activate", self.remove_history_items)
        self.add_action(action3)
        
        self.version = version
        self.app_name = app_name

    def on_activate(self, app):
        self.win = MainWindow(application=app, app_name=self.app_name)
        self.win.present()
        
    def create_new_tab(self, action, param):
        self.win.create_new_tab()
        
    def remove_history_items(self, action, param):
        self.win.remove_history_items()
        
    def show_about_dialog(self, action, param):
        about_dialog = Gtk.AboutDialog()
        about_dialog.set_program_name(self.app_name)
        about_dialog.set_version(self.version)
        about_dialog.set_copyright(f"© {datetime.now().year} Twilight, Inc")
        about_dialog.set_comments("A simple web browser written in Python, GTK4, libadwaita, and WebKitGTK.")
        about_dialog.set_license_type(Gtk.License.GPL_3_0)
        about_dialog.set_authors(["RedVelvetCake11"])
        about_dialog.set_website("https://rvc11.is-a.dev/weaver")

        about_dialog.present()

def main(version, app_name):
    app = MyApp(application_id="org.twilight.weaver", version=version, app_name=app_name)
    return app.run(sys.argv)

if __name__ == '__main__':
    if not os.path.exists(os.path.expanduser('~/.weaver')):
        os.makedirs(os.path.expanduser('~/.weaver'), exist_ok=True)  # Create ~/.weaver if it doesn't exist'/.weaver')
    main('1.0', 'Weaver')