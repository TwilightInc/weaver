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
gi.require_version('GObject', '2.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, WebKit, Gio, GLib, Gdk, GdkPixbuf, GObject
from PIL import Image  # Import the Pillow library for image conversion
import configparser
import hashlib
import adblockeryt as yt

os.environ['GTK_INSPECTOR'] = '1'

class PreferencesDialog(Adw.PreferencesDialog):
    """
    A simple preferences dialog with:
      - A toggle to override website fonts (off by default)
      - A font chooser (enabled only if toggle is on)
      - A basic 'search' entry at the top
    """
    def __init__(self, parent, webview_settings: WebKit.Settings):
        super().__init__()
        self.set_title("Preferences")
 
        self._webview_settings = webview_settings
 
        # Main container
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        self.set_child(box)
 
        hb = Adw.HeaderBar()
        self.set_title("Preferences")
        hb.get_style_context().add_class("headerbar")
        box.append(hb)

        # 1) Search bar
        search_label = Gtk.Label(label="Search Preferences:", halign=Gtk.Align.START)
        search_entry = Gtk.SearchEntry()
        searchbar = Gtk.SearchBar()
        searchbar.connect_entry(search_entry)
        searchbar.set_show_close_button(False)
        searchbar.set_child(search_entry)
        box.append(searchbar)
 
        button = Gtk.ToggleButton()
        button.set_icon_name("system-search-symbolic")
        button.bind_property("active", searchbar, "search-mode-enabled", GObject.BindingFlags.BIDIRECTIONAL)
        hb.pack_start(button)

        searchbar.set_key_capture_widget(self)
 
        font_override_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        font_override_setting = Adw.PreferencesGroup()
        font_override_setting.set_title("Font Override")
        font_override_setting_1 = Adw.SwitchRow()
        font_override_setting_1.set_title("Enable font overriding")
        font_override_setting.add(font_override_setting_1)
        font_override_setting_1.connect("notify::active", self.on_font_override_toggled)
        font_override_box.append(font_override_setting)
 
        box2.append(font_override_box)
 
        # 3) Font chooser
        self.font_button = Gtk.FontButton()
        self.font_button.set_use_font(True)
        self.font_button.set_use_size(False)
        self.font_button.set_hexpand(True)
        self.font_button.set_sensitive(False)
        self.font_button.connect("font-set", self.on_font_picked)

        font_override_setting_2 = Adw.ActionRow()
        font_override_setting_2.set_title("Choose a font")
        font_override_setting_2.add_suffix(self.font_button)
        font_override_setting.add(font_override_setting_2)
 
        box2.append(self.font_button)

        box.append(box2)

    def apply_hb_style(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        .headerbar {
            background-color: transparent;
        }
        """)

        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
     
    def on_font_override_toggled(self, switch, state):
        """Enable or disable the font chooser when toggle is flipped."""
        self.font_button.set_sensitive(state)
 
        if not state:
            # Reset to WebKit default if turning off override
            WebKit.Settings.set_sans_serif_font_family(self._webview_settings, "sans-serif")
 
    def on_font_picked(self, font_button: Gtk.FontButton):
        """When the user picks a font, override the web view's font setting."""
        chosen_font = font_button.get_font()
        # The 'default-font-family' property in WebKit2.Settings
        # sets the general default font.  If you also want to handle
        # monospace or serif fonts, you'd set those too.
        WebKit.Settings.set_sans_serif_font_family(self._webview_settings, chosen_font)

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

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, version, app_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hb = Adw.HeaderBar()
        self.settings = Gtk.Settings.get_default()
        self.dark_mode = self.settings.get_property("gtk-application-prefer-dark-theme")
        self.app_name = app_name
        self.weaver_title = None
        self.is_weaver_url = False
        self.weaver_url = None
        self.adblocker_yt_js = yt.get_javascript()
        self.version = version

        # Create a Box for layout
        self.a = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Create TabView and TabBar
        self.a.append(self.hb)
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
        self.url_entry.connect("changed", self.on_url_changed)  # Connect signal when text changes
        self.url_entry.connect("activate", self.on_url_activated)  # Connect signal when Enter is pressed
        self.url_entry.set_width_chars(80)
        # Set the Entry widget as the title widget in the HeaderBar
        self.hb.set_title_widget(self.url_entry)
        self.set_title("Weaver")

        # Add the layout (Box) to the window
        self.set_content(self.a)

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
            if len(title) > 20:
                title = title[:20] + "..."
            menu_item = Gio.MenuItem.new(f"{title}", f"app.history_item('{url}')")
            history_items.append_item(menu_item)
            
        history_submenu.append_section(None, options)
        history_submenu.append_section("Recent history", history_items)

    def change_url(self, url):
        # Handle URL change
        current_tab = self.tab_view.get_selected_page()
        webview = current_tab.get_child()
        if isinstance(webview, WebKit.WebView):
            webview.load_uri(url)
            
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
            menu_item = Gio.MenuItem.new(title, f"app.bookmark_item('{url}')")
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
        current_tab = self.tab_view.get_selected_page()
        webview = current_tab.get_child()

        url = entry.get_text()
        if url.startswith("file://") or url.startswith("weaver://"):
            url = url
        elif url.startswith("about:blank"):
            if isinstance(webview, WebKit.WebView):
                webview.load_html('<html></html>')
        elif not re.search(r'.*\.[a-z]{2,6}(/.*)?$', url):
            url = f"https://www.duckduckgo.com/?q={url}"
        elif not url.startswith("http://") and not url.startswith("https://"):
            url = "http://" + url

        if isinstance(webview, WebKit.WebView):
            if url.startswith("weaver://"):
                self.is_weaver_url = True
                self.weaver_url = url
                self.load_weaver_page(url.replace("weaver://", ""))
            else:
                self.is_weaver_url = False
                self.weaver_url = None
                webview.load_uri(url)

        # Update navigation buttons after URL change
        self.update_navigation_buttons(webview)

    def load_weaver_page(self, url):
        current_tab = self.tab_view.get_selected_page()
        webview = current_tab.get_child()
        if isinstance(webview, WebKit.WebView):
            if url == "home":
                webview.load_html('test')
            elif url == "about":
                self.weaver_title = f"About {self.app_name}"
                webview.load_html(f"""
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en" dir="ltr">
<head>
  <meta http-equiv="content-type" content="text/html; charset=utf-8">
  <meta http-equiv="weaver-url" content="{url}">
  <title>{self.weaver_title}</title>
  <style>
    /* Global CSS for error pages */
    :root {{ 
        --bg-color: {'#242424' if self.dark_mode else '#fafafa'}; 
        --fg-color: {'rgba(255, 255, 255, 0.8)' if self.dark_mode else 'rgba(0, 0, 0, 0.8)'}; 
        --base-color: {'#000' if self.dark_mode else '#fff'}; 
        --text-color: {'#fff' if self.dark_mode else '#000'}; 
        --borders: #d3d7cf; 
        --error-color: #c01c28;
        --icon-invert: 0.2; /* icon color adjustment */
        --error-filter: hue-rotate(-5.1deg) grayscale(45%) brightness(144%);
        color-scheme: light dark;
    }}
    body {{
        font-family: -webkit-system-font, Cantarell, sans-serif;
        color: var(--fg-color);
        background-color: var(--bg-color);
        height: 100%;
    }}
    .error-body {{
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        justify-content: center;
        max-width: 40em;
        margin: auto;
        padding-left: 12px;
        padding-right: 12px;
        line-height: 1.5;
        height: 100%;
    }}
    .clickable {{
        cursor: pointer;
        opacity: 0.6;
    }}
    .clickable:hover, .clickable:focus {{
        opacity: 0.8;
    }}
    #msg-title {{
        text-align: center;
        font-size: 20pt;
        font-weight: 800;
    }}
    #msg-subtitle {{
        text-align: center;
        font-size: 20pt;
        font-weight: 800;
        margin-top: 0px;
        margin-bottom: 10px;
    }}
    #msg-icon {{
        margin-left: auto;
        margin-right: auto;
        width: 128px;
        height: 128px;
        background-size: cover;
    }}
    #msg-details {{
        margin-top: 10px;
        margin-bottom: 10px;
    }}
    #msg-body {{
        text-align: center; 
    }}
    .btn {{
        min-width: 200px;
        height: 32px;
        margin-top: 15px;
        margin-bottom: 0;
        line-height: 1.42857143;
        text-align: center;
        white-space: nowrap;
        vertical-align: middle;
        cursor: pointer;
        border: none;
        border-radius: 5px;
    }}
    .suggested-action {{
        color: white;
        background-color: #3584e4;
    }}
    .suggested-action:hover, .suggested-action:focus, .suggested-action:active {{
        color: white;
        background-color: #3987e5;
    }}
    .destructive-action {{
        color: white;
        background-color: #e01b24;
    }}
    .destructive-action:hover, .destructive-action:focus, .destructive-action:active {{
        color: white;
        background-color: #e41c26;
    }}
  </style>
</head>
<body class="error-body">
  <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" id="msg-icon" width="128" height="128"><defs><clipPath id="i"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="Y"><path d="M79 0h49v128H79zm0 0"/></clipPath><clipPath id="b"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="Z"><path d="M479.988 20.078c0 110.453-89.543 200-200 200-110.453 0-200-89.547-200-200 0-110.457 89.547-200 200-200 110.457 0 200 89.543 200 200zm0 0"/></clipPath><clipPath id="c"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="q"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="p"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="d"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="o"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="e"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="n"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="f"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="m"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="g"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="l"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="h"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="k"><path d="M0 0h192v152H0z"/></clipPath><clipPath id="j"><path d="M0 0h192v152H0z"/></clipPath><mask id="S"><g filter="url(#a)"><path fill-opacity=".668" d="M0 0h128v128H0z"/></g></mask><mask id="ab"><g filter="url(#a)"><path fill-opacity=".5" d="M0 0h128v128H0z"/></g></mask><mask id="M"><g filter="url(#a)"><path fill-opacity=".1" d="M0 0h128v128H0z"/></g></mask><mask id="I"><g filter="url(#a)"><path fill-opacity=".1" d="M0 0h128v128H0z"/></g></mask><mask id="O"><g filter="url(#a)"><path fill-opacity=".1" d="M0 0h128v128H0z"/></g></mask><mask id="G"><g filter="url(#a)"><path fill-opacity=".1" d="M0 0h128v128H0z"/></g></mask><mask id="Q"><g filter="url(#a)"><path fill-opacity=".668" d="M0 0h128v128H0z"/></g></mask><mask id="E"><g filter="url(#a)"><path fill-opacity=".1" d="M0 0h128v128H0z"/></g></mask><mask id="t"><g filter="url(#a)"><path fill-opacity=".1" d="M0 0h128v128H0z"/></g></mask><mask id="C"><g filter="url(#a)"><path fill-opacity=".1" d="M0 0h128v128H0z"/></g></mask><mask id="U"><g filter="url(#a)"><path fill-opacity=".668" d="M0 0h128v128H0z"/></g></mask><mask id="A"><g filter="url(#a)"><path fill-opacity=".1" d="M0 0h128v128H0z"/></g></mask><mask id="W"><g filter="url(#a)"><path fill-opacity=".3" d="M0 0h128v128H0z"/></g></mask><mask id="y"><g filter="url(#a)"><path fill-opacity=".1" d="M0 0h128v128H0z"/></g></mask><mask id="v"><g filter="url(#a)"><path fill-opacity=".2" d="M0 0h128v128H0z"/></g></mask><mask id="K"><g filter="url(#a)"><path fill-opacity=".1" d="M0 0h128v128H0z"/></g></mask><g id="F" clip-path="url(#h)"><path d="M103.586 65.293h4v2h-4zm0 0" fill="#fff"/></g><g id="N" clip-path="url(#l)"><path d="M63.586 47.293h4v2h-4zm0 0" fill="#fff"/></g><g id="x" clip-path="url(#d)"><path d="M85.586 97.293h6v2h-6zm0 0" fill="#fff"/></g><g id="B" clip-path="url(#f)"><path d="M39.586 43.293h6v2h-6zm0 0" fill="#fff"/></g><g id="P" clip-path="url(#m)"><path d="M66.8 66.254c0 6.617-5.362 11.98-11.98 11.98-6.613 0-11.976-5.363-11.976-11.98s5.363-11.98 11.976-11.98c6.617 0 11.98 5.363 11.98 11.98zm0 0" fill="none" stroke-width="5.59" stroke-linejoin="round" stroke="#fff"/></g><g id="H" clip-path="url(#i)"><path d="M103.586 71.293h2v2h-2zm0 0" fill="#fff"/></g><g id="aa" clip-path="url(#q)"><path d="M169.336 19.172v3.531l.883.883.34.344.543-.543v-.684h.683l.2-.2v-.683l.882-.883h.684l.199-.199v-.683l-.883-.883zm8.113 0v1.765h1.598l.91 1.325v.441l.856.883v-4.414zm3.363 4.414l-.91.05-.855-.933v-.219h-1.078l-.442-.664h-.078v2.883l.301.43v1.762L179.047 28l.883-.883V24.47zm0 0" fill="#2e3436"/></g><g id="R" clip-path="url(#n)"><path d="M77.602 66.254c0 12.582-10.2 22.781-22.782 22.781-12.578 0-22.777-10.2-22.777-22.781 0-12.582 10.2-22.781 22.777-22.781 12.582 0 22.782 10.199 22.782 22.78zm0 0" fill="none" stroke-width="3.862" stroke-linejoin="round" stroke="#fff"/></g><g id="s" clip-path="url(#b)"><path d="M107.586 115.293v14a60.121 60.121 0 0012-12v-2zm0 0" fill="#fff"/></g><g id="J" clip-path="url(#j)"><path d="M113.586 71.293h6v2h-6zm0 0" fill="#fff"/></g><g id="T" clip-path="url(#o)"><path d="M88.879 66.254c0 18.808-15.246 34.058-34.059 34.058-18.808 0-34.058-15.25-34.058-34.058 0-18.813 15.25-34.059 34.058-34.059 18.813 0 34.059 15.246 34.059 34.059zm0 0" fill="none" stroke-width="1.98" stroke-linejoin="round" stroke="#fff"/></g><g id="D" clip-path="url(#g)"><path d="M47.586 67.293h4v2h-4zm0 0" fill="#fff"/></g><g id="z" clip-path="url(#e)"><path d="M33.586 77.293h4v2h-4zm0 0" fill="#fff"/></g><g id="V" clip-path="url(#p)"><path d="M55.176 70.605L17.512 107.16a59.63 59.63 0 006.293 10.336l5.379.176-1.914 3.973a60.081 60.081 0 009.851 8.722l3.3-7.43 15.067 16.094c.13.031.258.067.387.098zm0 0" fill-rule="evenodd" fill="#12121c"/></g><g id="L" clip-path="url(#k)"><path d="M101.586 45.148h4v2h-4zm0 0" fill="#fff"/></g><g id="u" clip-path="url(#c)"><path d="M71.586 21.293a60.068 60.068 0 00-24.477 5.219l8.477 6.781v8l8 8h4v-4l6-6v-4l4-4v-9.7c-1.992-.198-3.996-.3-6-.3zm-40.79 16a59.996 59.996 0 00-19.085 40.113l19.875 17.887v-6l-4-4 6-6h4l4 4 .125-8.402 5.875-5.598h4v-4l4-4v-6l-4.273-3.875-9.727-.125v8h-4l-4-4v-4l6-6h6v-4l-4-4zm70.79 2l-6 6v4h6v-2.145h4v4.27l-2 1.875h-10v4h-4v6h-8v8h10v-4h8v2l4 4h2v-2l-2-2v-2h4l6 6h6v2l-2 2h-4l16.652 16.652a60.002 60.002 0 00-15.805-54.652zm12 38h-12l-2-2h-14l-8 8v8l8 8h6l4 4v2l2 2v12l10 10a60.02 60.02 0 0012-12v-14l4-4v-8l-10-10zm-2-12h4l6 6h-4zm-74 28l-4 4v10l8.125 8.144-.086 17.836a59.466 59.466 0 007.96 3.84v-3.82l6-6v-4l6-6v-4l4-4v-8l-4-4h-8l-4-4zm0 0"/></g><radialGradient id="X" gradientUnits="userSpaceOnUse" cx="17.814" cy="24.149" fx="17.814" fy="24.149" r="9.125" gradientTransform="matrix(7.42904 0 0 7.1212 -88.327 -114.956)"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#e4e4e4"/></radialGradient><radialGradient id="w" gradientUnits="userSpaceOnUse" cx="46.511" cy="236.83" fx="46.511" fy="236.83" r="224" gradientTransform="matrix(.29041 -.00079 .00067 .24464 49.921 -16.608)"><stop offset="0" stop-color="#cee2f8"/><stop offset=".552" stop-color="#98c1f1"/><stop offset="1" stop-color="#62a0ea"/></radialGradient><radialGradient id="r" gradientUnits="userSpaceOnUse" cx="256" cy="-46.416" fx="256" fy="-46.416" r="224" gradientTransform="matrix(.29048 0 0 .29907 -10.777 55.175)"><stop offset="0" stop-color="#62a0ea"/><stop offset=".552" stop-color="#3584e4"/><stop offset="1" stop-color="#1a5fb4"/></radialGradient><filter id="a" filterUnits="objectBoundingBox" x="0%" y="0%" width="100%" height="100%"><feColorMatrix in="SourceGraphic" values="0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 1 0"/></filter></defs><path d="M39.11 8.512v2l4.011-.16.09-1.997zm0 0" fill-rule="evenodd" fill="#2967b4"/><path d="M3.71 59.41v2l4.013-.16.09-1.996zm0 0" fill-rule="evenodd" fill="#164e93"/><path d="M123.586 65.293c0 33.137-26.863 60-60 60s-60-26.863-60-60 26.863-60 60-60 60 26.863 60 60zm0 0" fill="url(#r)"/><use xlink:href="#s" transform="translate(-8 -16)" mask="url(#t)"/><use xlink:href="#u" transform="translate(-8 -16)" mask="url(#v)"/><path d="M105.586 59.293v2h4v-2zm0 0" fill-rule="evenodd" fill="#144788"/><path d="M63.586 3.293a60.068 60.068 0 00-24.477 5.219l8.477 6.781v8l8 8h4v-4l6-6v-4l4-4v-9.7c-1.992-.198-3.996-.3-6-.3zm-40.79 16A59.996 59.996 0 003.712 59.406l19.875 17.887v-6l-4-4 6-6h4l4 4 .125-8.402 5.875-5.598h4v-4l4-4v-6l-4.273-3.875-9.727-.125v8h-4l-4-4v-4l6-6h6v-4l-4-4zm70.79 2l-6 6v4h6v-2.145h4v4.27l-2 1.875h-10v4h-4v6h-8v8h10v-4h8v2l4 4h2v-2l-2-2v-2h4l6 6h6v2l-2 2h-4l16.652 16.652a60.002 60.002 0 00-15.805-54.652zm12 38h-12l-2-2h-14l-8 8v8l8 8h6l4 4v2l2 2v12l10 10a60.02 60.02 0 0012-12v-14l4-4v-8l-10-10zm-2-12h4l6 6h-4zm-74 28l-4 4v10l8.125 8.144-.086 17.836a59.466 59.466 0 007.96 3.84v-3.82l6-6v-4l6-6v-4l4-4v-8l-4-4h-8l-4-4zm0 0" fill="url(#w)"/><use xlink:href="#x" transform="translate(-8 -16)" mask="url(#y)"/><use xlink:href="#z" transform="translate(-8 -16)" mask="url(#A)"/><use xlink:href="#B" transform="translate(-8 -16)" mask="url(#C)"/><use xlink:href="#D" transform="translate(-8 -16)" mask="url(#E)"/><use xlink:href="#F" transform="translate(-8 -16)" mask="url(#G)"/><use xlink:href="#H" transform="translate(-8 -16)" mask="url(#I)"/><use xlink:href="#J" transform="translate(-8 -16)" mask="url(#K)"/><use xlink:href="#L" transform="translate(-8 -16)" mask="url(#M)"/><use xlink:href="#N" transform="translate(-8 -16)" mask="url(#O)"/><use xlink:href="#P" transform="translate(-8 -16)" mask="url(#Q)"/><use xlink:href="#R" transform="translate(-8 -16)" mask="url(#S)"/><use xlink:href="#T" transform="translate(-8 -16)" mask="url(#U)"/><use xlink:href="#V" transform="translate(-8 -16)" mask="url(#W)"/><path d="M47.176 50.605L-.59 96.97l21.774.703-9.13 18.965c-2.812 8.43 9.833 11.59 11.942 5.27l8.43-18.97 15.453 16.508zm0 0" fill-rule="evenodd" fill="url(#X)"/><path d="M47.176 50.605l-.246.239-31.16 73.781c3.148 1.277 7.12.586 8.222-2.719l8.43-18.969 15.457 16.508zm0 0" fill-rule="evenodd" fill="#e4e6e8"/><g clip-path="url(#Y)"><g clip-path="url(#Z)"><use xlink:href="#aa" transform="translate(-8 -16)" mask="url(#ab)"/></g></g></svg>
  <h1 id="msg-title">Weaver</h1>
  <h2 id="msg-subtitle" style="opacity: 0.55;">Version {self.version}</h2>
  <p id="msg-body">A simple web browser written in Python, GTK4, libadwaita, and WebKitGTK</p>
</body>
</html>
""")
            elif url == "start":
                self.weaver_title = f"Welcome to {self.app_name}"
                webview.load_html(f"""
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en" dir="ltr">
<head>
  <meta http-equiv="content-type" content="text/html; charset=utf-8">
  <title>{self.weaver_title}</title>
  <style>
    /* Global CSS for error pages */
    :root {{ 
        --bg-color: {'#242424' if self.dark_mode else '#fafafa'}; 
        --fg-color: {'rgba(255, 255, 255, 0.8)' if self.dark_mode else 'rgba(0, 0, 0, 0.8)'}; 
        --base-color: {'#000' if self.dark_mode else '#fff'}; 
        --text-color: {'#fff' if self.dark_mode else '#000'}; 
        --borders: #d3d7cf; 
        --error-color: #c01c28;
        --icon-invert: 0.2; /* icon color adjustment */
        --error-filter: hue-rotate(-5.1deg) grayscale(45%) brightness(144%);
        color-scheme: light dark;
    }}
    body {{
        font-family: -webkit-system-font, Cantarell, sans-serif;
        color: var(--fg-color);
        background-color: var(--bg-color);
        height: 100%;
    }}
    .error-body {{
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        justify-content: center;
        max-width: 40em;
        margin: auto;
        padding-left: 12px;
        padding-right: 12px;
        line-height: 1.5;
        height: 100%;
    }}
    .clickable {{
        cursor: pointer;
        opacity: 0.6;
    }}
    .clickable:hover, .clickable:focus {{
        opacity: 0.8;
    }}
    #msg-title {{
        text-align: center;
        font-size: 20pt;
        font-weight: 800;
    }}
    #msg-icon {{
        margin-left: auto;
        margin-right: auto;
        width: 128px;
        height: 128px;
        background-size: cover;
        opacity: 0.5;
        filter: brightness(0) invert(var(--icon-invert));
    }}
    #msg-details {{
        margin-top: 10px;
        margin-bottom: 10px;
    }}
    .btn {{
        min-width: 200px;
        height: 32px;
        margin-top: 15px;
        margin-bottom: 0;
        line-height: 1.42857143;
        text-align: center;
        white-space: nowrap;
        vertical-align: middle;
        cursor: pointer;
        border: none;
        border-radius: 5px;
    }}
    .suggested-action {{
        color: white;
        background-color: #3584e4;
    }}
    .suggested-action:hover, .suggested-action:focus, .suggested-action:active {{
        color: white;
        background-color: #3987e5;
    }}
    .destructive-action {{
        color: white;
        background-color: #e01b24;
    }}
    .destructive-action:hover, .destructive-action:focus, .destructive-action:active {{
        color: white;
        background-color: #e41c26;
    }}
  </style>
</head>
<body class="error-body">
  <h1 id="msg-title">Work in progress</h1>
  <p>This page is currently under construction.</p>
  <p>Expect to see some changes soon.</p>
  <div>
    <button class="btn suggested-action" onclick="">Suggest a feature</button>
  </div>
</body>
</html>
""")
            else:
                self.weaver_title = "Problem Loading Page"
                webview.load_html(f"""
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en" dir="ltr">
<head>
  <meta http-equiv="content-type" content="text/html; charset=utf-8">
  <meta http-equiv="weaver-url" content="{url}">
  <title>{self.weaver_title}</title>
  <style>
    /* Global CSS for error pages */
    :root {{ 
        --bg-color: {'#242424' if self.dark_mode else '#fafafa'}; 
        --fg-color: {'rgba(255, 255, 255, 0.8)' if self.dark_mode else 'rgba(0, 0, 0, 0.8)'}; 
        --base-color: {'#000' if self.dark_mode else '#fff'}; 
        --text-color: {'#fff' if self.dark_mode else '#000'}; 
        --borders: #d3d7cf; 
        --error-color: #c01c28;
        --icon-invert: 0.2; /* icon color adjustment */
        --error-filter: hue-rotate(-5.1deg) grayscale(45%) brightness(144%);
        color-scheme: light dark;
    }}
    body {{
        font-family: -webkit-system-font, Cantarell, sans-serif;
        color: var(--fg-color);
        background-color: var(--bg-color);
        height: 100%;
    }}
    .error-body {{
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        justify-content: center;
        max-width: 40em;
        margin: auto;
        padding-left: 12px;
        padding-right: 12px;
        line-height: 1.5;
        height: 100%;
    }}
    .clickable {{
        cursor: pointer;
        opacity: 0.6;
    }}
    .clickable:hover, .clickable:focus {{
        opacity: 0.8;
    }}
    #msg-title {{
        text-align: center;
        font-size: 20pt;
        font-weight: 800;
    }}
    #msg-icon {{
        margin-left: auto;
        margin-right: auto;
        width: 128px;
        height: 128px;
        background-size: cover;
        opacity: 0.5;
        filter: brightness(0) invert(var(--icon-invert));
    }}
    #msg-details {{
        margin-top: 10px;
        margin-bottom: 10px;
    }}
    .btn {{
        min-width: 200px;
        height: 32px;
        margin-top: 15px;
        margin-bottom: 0;
        line-height: 1.42857143;
        text-align: center;
        white-space: nowrap;
        vertical-align: middle;
        cursor: pointer;
        border: none;
        border-radius: 5px;
    }}
    .suggested-action {{
        color: white;
        background-color: #3584e4;
    }}
    .suggested-action:hover, .suggested-action:focus, .suggested-action:active {{
        color: white;
        background-color: #3987e5;
    }}
    .destructive-action {{
        color: white;
        background-color: #e01b24;
    }}
    .destructive-action:hover, .destructive-action:focus, .destructive-action:active {{
        color: white;
        background-color: #e41c26;
    }}
  </style>
</head>
<body class="error-body">
  <h1 id="msg-title">Invalid URL</h1>
  <p>The URL cannot be recognized by Weaver</p>
</body>
</html>
""")
        
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
            if self.is_weaver_url == False:
                webview.reload()
            else:
                self.load_weaver_page(self.weaver_url.replace("weaver://", ""))
            
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
            if self.weaver_url and self.is_weaver_url == False:
                self.is_weaver_url = True
            else:
                self.is_weaver_url = False
            
            current_url = self.weaver_url if self.is_weaver_url else webview.get_uri()
            self.url_entry.set_text(current_url if current_url else '')

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
            self.reload_icon.set_from_icon_name("view-refresh-symbolic")
            self.update_navigation_buttons(webview)

            if current_url == "about:blank" and self.is_weaver_url == False:
                selected_tab.set_title("Untitled")
            elif self.is_weaver_url:
                self.url_entry.set_text(self.weaver_url)
                self.tab_view.get_selected_page().set_title(self.weaver_title)
                self.set_title(f"{self.weaver_title} - Weaver")
                self.add_to_history(self.weaver_url, self.weaver_title)
                self.populate_history_submenu(self.history_submenu)
                self.is_weaver_url = False
            elif current_url != f'about:blank':
                self.url_entry.set_text(current_url)

                if current_url.startswith("https://"):
                    # Set lock icon for the URL entry
                    self.url_entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "system-lock-screen")

                # Fetch the HTML page to update the title
                self.tab_view.get_selected_page().set_title(webview.get_title() if webview.get_title() else 'Untitled')
                self.set_title(f"{webview.get_title()} - Weaver")
                    
                if current_url.startswith("http://") or current_url.startswith("https://"):
                    self.current_url_to_bookmark = current_url
                    self.update_icon(current_url)
                    
                # Save to history
                self.add_to_history(current_url, webview.get_title())
                
                # Add bookmark functionality
                self.populate_history_submenu(self.history_submenu)

                if "www.youtube.com" in current_url:
                    WebKit.WebView.evaluate_javascript(webview, self.adblocker_yt_js, len(self.adblocker_yt_js), None, None)

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
            self.add_bookmark(url, name)
            self.populate_bookmarks_menu()
        dialog.close()
          
    def update_navigation_buttons(self, webview):
        if webview:
            self.back_button.set_sensitive(webview.can_go_back())
            self.forward_button.set_sensitive(webview.can_go_forward())

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
        menu.append("Preferences", "app.preferences")
        menu.append(f"About {self.app_name}", "app.about")  # Menu item "About"

        # Set the menu to the button
        menu_button.set_menu_model(menu)
        self.hb.pack_end(menu_button)

    def create_new_tab(self, url=None):
        webview = WebKit.WebView()
        webview.connect("context-menu", self.on_context_menu)
        inspector = WebKit.WebView.get_inspector(webview)
        inspector.connect("attach", self.on_attach_inspector, webview)
        title = "New tab"
        tab = self.tab_view.append(webview)
        tab.set_title(title)
        self.tab_view.set_selected_page(tab)
        self.load_weaver_page("start")
        webview.connect("load-changed", self.on_webview_load_changed)
        webview.connect("load-failed", self.on_webview_load_failed)
        self.webview_settings = webview.get_settings()
 

    def on_context_menu(self, webview, context_menu, hit_test_result):
        WebKit.ContextMenu.append(context_menu, WebKit.ContextMenuItem.new_separator())
        WebKit.ContextMenu.append(context_menu, WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.INSPECT_ELEMENT))

    def on_attach_inspector(self, inspector, webview):
        print(inspector)
        print(webview)
        inspector.show()

    def on_new_tab_clicked(self, button):
        self.create_new_tab()

    def on_test_button_clicked(self, button):
        width = self.get_width()
        print(f"Window width: {width}")

    def on_webview_load_failed(self, webview, frame, error, failed_uri):
        # This method will be called when page loading fails (e.g., connection refused)
        
        # Prepare the error page HTML
        error_page_html = f"""
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en" dir="ltr">
<head>
  <meta http-equiv="content-type" content="text/html; charset=utf-8">
  <title>Problem Loading Page</title>
  <style>
    /* Global CSS for error pages */
    :root {{ 
        --bg-color: {'#242424' if self.dark_mode else '#fafafa'}; 
        --fg-color: {'rgba(255, 255, 255, 0.8)' if self.dark_mode else 'rgba(0, 0, 0, 0.8)'}; 
        --base-color: {'#000' if self.dark_mode else '#fff'}; 
        --text-color: {'#fff' if self.dark_mode else '#000'}; 
        --borders: #d3d7cf; 
        --error-color: #c01c28;
        --icon-invert: 0.2; /* icon color adjustment */
        --error-filter: hue-rotate(-5.1deg) grayscale(45%) brightness(144%);
        color-scheme: light dark;
    }}
    body {{
        font-family: -webkit-system-font, Cantarell, sans-serif;
        color: var(--fg-color);
        background-color: var(--bg-color);
        height: 100%;
    }}
    .error-body {{
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        justify-content: center;
        max-width: 40em;
        margin: auto;
        padding-left: 12px;
        padding-right: 12px;
        line-height: 1.5;
        height: 100%;
    }}
    .clickable {{
        cursor: pointer;
        opacity: 0.6;
    }}
    .clickable:hover, .clickable:focus {{
        opacity: 0.8;
    }}
    #msg-title {{
        text-align: center;
        font-size: 20pt;
        font-weight: 800;
    }}
    #msg-icon {{
        margin-left: auto;
        margin-right: auto;
        width: 128px;
        height: 128px;
        background-size: cover;
        opacity: 0.5;
        filter: brightness(0) invert(var(--icon-invert));
    }}
    #msg-details {{
        margin-top: 10px;
        margin-bottom: 10px;
    }}
    .btn {{
        min-width: 200px;
        height: 32px;
        margin-top: 15px;
        margin-bottom: 0;
        line-height: 1.42857143;
        text-align: center;
        white-space: nowrap;
        vertical-align: middle;
        cursor: pointer;
        border: none;
        border-radius: 5px;
    }}
    .suggested-action {{
        color: white;
        background-color: #3584e4;
    }}
    .suggested-action:hover, .suggested-action:focus, .suggested-action:active {{
        color: white;
        background-color: #3987e5;
    }}
    .destructive-action {{
        color: white;
        background-color: #e01b24;
    }}
    .destructive-action:hover, .destructive-action:focus, .destructive-action:active {{
        color: white;
        background-color: #e41c26;
    }}
  </style>
</head>
<body class="error-body">
  <svg id="msg-icon" xmlns="http://www.w3.org/2000/svg" viewbox="0 0 24 24" height="128px" width="128px">
    <g fill="#222222">
      <path d="m 9 8 c -0.554688 0 -1 0.445312 -1 1 v 6 c 0 0.554688 0.445312 1 1 1 h 6 c 0.554688 0 1 -0.445312 1 -1 v -6 c 0 -0.554688 -0.445312 -1 -1 -1 z m 0 1 h 1 c 0.242188 0.007812 0.421875 0.082031 0.6875 0.3125 l 1.308594 1.277344 l 1.28125 -1.277344 c 0.183594 -0.1875 0.425781 -0.296875 0.6875 -0.3125 h 1.03125 v 1 c 0.027344 0.28125 -0.078125 0.554688 -0.28125 0.746094 l -1.28125 1.28125 l 1.28125 1.25 c 0.1875 0.1875 0.28125 0.453125 0.28125 0.71875 v 1 h -1 c -0.265625 -0.007813 -0.53125 -0.09375 -0.71875 -0.28125 l -1.28125 -1.28125 l -1.277344 1.28125 c -0.179688 0.199218 -0.453125 0.28125 -0.71875 0.28125 h -1 v -1 c -0.007812 -0.269532 0.09375 -0.527344 0.28125 -0.71875 l 1.246094 -1.25 l -1.277344 -1.28125 c -0.214844 -0.199219 -0.25 -0.460938 -0.25 -0.746094 z m 0 0"/>
      <path d="m 7.5 0 c -4.128906 0 -7.5 3.371094 -7.5 7.5 c 0 3.960938 3.101562 7.222656 7 7.480469 v -2.199219 c -0.039062 -0.03125 -0.078125 -0.0625 -0.117188 -0.105469 c -0.234374 -0.238281 -0.480468 -0.625 -0.6875 -1.125 c -0.375 -0.898437 -0.632812 -2.152343 -0.683593 -3.550781 h 1.488281 v -1 h -1.488281 c 0.046875 -1.398438 0.308593 -2.65625 0.683593 -3.550781 c 0.207032 -0.503907 0.453126 -0.886719 0.6875 -1.125 c 0.234376 -0.238281 0.433594 -0.324219 0.617188 -0.324219 s 0.382812 0.085938 0.617188 0.324219 c 0.234374 0.238281 0.480468 0.625 0.6875 1.125 c 0.375 0.898437 0.632812 2.152343 0.683593 3.550781 h 1 c -0.050781 -1.515625 -0.320312 -2.882812 -0.757812 -3.9375 c -0.109375 -0.253906 -0.230469 -0.503906 -0.375 -0.742188 c 2.019531 0.71875 3.433593 2.546876 3.621093 4.679688 h 2.003907 c -0.257813 -3.898438 -3.519531 -7 -7.480469 -7 z m -1.855469 2.320312 c -0.144531 0.238282 -0.265625 0.488282 -0.375 0.742188 c -0.4375 1.054688 -0.707031 2.421875 -0.757812 3.9375 h -2.488281 c 0.1875 -2.132812 1.601562 -3.960938 3.621093 -4.679688 z m -3.621093 5.679688 h 2.488281 c 0.050781 1.515625 0.320312 2.882812 0.757812 3.9375 c 0.113281 0.269531 0.238281 0.515625 0.375 0.742188 c -2.019531 -0.71875 -3.433593 -2.546876 -3.621093 -4.679688 z m 0 0" fill-opacity="0.34902"/>
    </g>
  </svg>
  <h1 id="msg-title">Unable to display this website</h1>
  <p>The site at <strong>{failed_uri}</strong> seems to be unavailable.</p>
  <p>It may be temporarily inaccessible or moved to a new address. You may wish to verify that your internet connection is working correctly.</p>
  <div id="msg-details" class="visible">
    <details>
      <summary class="clickable">Technical information</summary>
      <p>The precise error was: <i>{error}</i></p>
    </details>
  </div>
  <div>
    <button class="btn suggested-action" onclick="window.location.reload()">Reload</button>
  </div>
</body>
</html>
"""

        # Load the custom error page into the WebView
        self.get_current_webview().load_html(error_page_html)

# Main application class
class MyApp(Adw.Application):
    def __init__(self, version, app_name, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)
        
        self.version = version
        self.app_name = app_name
        
        action1 = Gio.SimpleAction.new("about", None)
        action1.connect("activate", self.show_about_dialog)
        self.add_action(action1)
        
        action2 = Gio.SimpleAction.new("new_tab", None)
        action2.connect("activate", self.create_new_tab)
        self.add_action(action2)
        
        action3 = Gio.SimpleAction.new("remove_history_items", None)
        action3.connect("activate", self.remove_history_items)
        self.add_action(action3)

        action4 = Gio.SimpleAction.new("history_item", GLib.VariantType("s"))
        action4.connect("activate", self.history_item)
        self.add_action(action4)

        action5 = Gio.SimpleAction.new("bookmark_item", GLib.VariantType("s"))
        action5.connect("activate", self.bookmark_item)
        self.add_action(action5)
        
        preferences_action = Gio.SimpleAction.new("preferences", None)
        preferences_action.connect("activate", self.on_preferences_activate)
        self.add_action(preferences_action)
 
    def on_preferences_activate(self, action, param):
        """Handler for the app.preferences menu item."""
        if not self.win:
            return
        # Create and show the preferences dialog
        dialog = PreferencesDialog(self.win, self.win.webview_settings)
        Adw.Dialog.present(dialog, self.win)
        
        self.version = self.version
        self.app_name = self.app_name

    def on_activate(self, app):
        self.win = MainWindow(version=self.version, application=app, app_name=self.app_name)
        self.win.present()

    def history_item(self, action, param):
        if param.get_string().startswith("weaver://"):
            self.win.is_weaver_url = True
            self.win.weaver_url = param.get_string()
            self.win.url_entry.set_text(param.get_string())
            self.win.load_weaver_page(param.get_string().replace("weaver://", ""))
        else:
            self.win.change_url(param.get_string())

    def bookmark_item(self, action, param):
        self.history_item(action, param)
        
    def create_new_tab(self, action, param):
        self.win.create_new_tab()
        
    def remove_history_items(self, action, param):
        self.win.remove_history_items()
        
    def show_about_dialog(self, action, param):
        about_dialog = Adw.AboutDialog()
        about_dialog.set_application_icon("org.twilight.weaver")
        about_dialog.set_application_name(self.app_name)
        about_dialog.set_version(self.version)
        about_dialog.set_copyright(f"© {datetime.now().year} Twilight, Inc")
        about_dialog.set_comments("A simple web browser written in Python, GTK4, libadwaita, and WebKitGTK")
        about_dialog.set_license_type(Gtk.License.GPL_3_0)
        about_dialog.set_developers(["RedVelvetCake11"])
        about_dialog.set_website("https://rvc11.is-a.dev/weaver")

        about_dialog.present(self.win)

def main(version, app_name):
    app = MyApp(application_id="org.twilight.weaver", version=version, app_name=app_name)
    return app.run(sys.argv)

if __name__ == '__main__':
    if not os.path.exists(os.path.expanduser('~/.weaver')):
        os.makedirs(os.path.expanduser('~/.weaver'), exist_ok=True)  # Create ~/.weaver if it doesn't exist'/.weaver')
    main('1.0', 'Weaver')
