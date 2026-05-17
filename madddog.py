#!/usr/bin/env python3

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import requests
import markdown2
# REPLACED: tkhtmlview with tkinterweb
from tkinterweb import HtmlFrame

class MarkdownExpertEditor:
    def __init__(self, root):
        self.root = root
        self.app_name = "MADDDOG Markdown Renderer"
        self.current_path = None
        self.is_modified = False
        self.active_model = None 
        self.debounce_timer = None
        
        # --- Set Window Icon ---
        try:
            if os.path.exists('madddog_logo.png'):
                self.logo_img = tk.PhotoImage(file='madddog_logo.png')
                self.root.iconphoto(False, self.logo_img)
        except Exception as e:
            print(f"Icon load failed: {e}")

        self.root.geometry("1200x800")
        self.setup_ui()
        self.setup_menu()
        self.update_window_title()
        
        # --- Display Logo on Startup ---
        self.display_welcome_logo()

        # --- Handle Command Line Argument ---
        if len(sys.argv) > 1:
            file_to_open = sys.argv[1]
            if os.path.exists(file_to_open):
                self.load_file_from_path(file_to_open)

    def setup_ui(self):
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=6, bg="#bdc3c7")
        self.paned.pack(fill=tk.BOTH, expand=True)

        is_mac = self.root.tk.call('tk', 'windowingsystem') == 'aqua'
        editor_font = ("Menlo", 11) if is_mac else ("Consolas", 10)

        self.left_paned = tk.PanedWindow(self.paned, orient=tk.VERTICAL, sashwidth=4, bg="#dcdde1")
        self.paned.add(self.left_paned, width=600)

        self.editor = tk.Text(self.left_paned, undo=True, font=editor_font,
                              wrap="word", padx=15, pady=15, bg="#ffffff", fg="#2c3e50", borderwidth=0)
        self.left_paned.add(self.editor, height=350)

        self.btn_frame = tk.Frame(self.left_paned, bg="#ecf0f1", height=45)
        self.submit_btn = tk.Button(self.btn_frame, text="⇧ Put your prompt here ⇧", command=self.run_ai_model,
                                    bg="#D2B48C", fg="black", relief="raised", padx=20, pady=5)
        self.submit_btn.pack(pady=5)

        self.response_area = tk.Text(self.left_paned, font=editor_font,
                                    wrap="word", padx=15, pady=15, bg="#f8f9fa", fg="#2f3640", borderwidth=0)
        
        # --- Right Side Preview Optimized via tkinterweb ---
        self.preview = HtmlFrame(self.paned, messages_enabled=False)
        self.paned.add(self.preview)

        self.status = tk.Label(self.root, text="Words: 0", anchor="w", padx=20, bg="#ecf0f1")
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        # FIXED: Bind modified track events to both left-pane text elements
        self.editor.bind("<<Modified>>", self.on_content_changed)
        self.response_area.bind("<<Modified>>", self.on_content_changed)

    def display_welcome_logo(self):
        if os.path.exists('madddog_logo.png'):
            abs_path = os.path.abspath("madddog_logo.png").replace("\\", "/")
            welcome_html = f"""
            <div align="center" style="padding-top: 50px;">
                <img src="file:///{abs_path}" width="400">
            </div>
            """
            self.preview.load_html(welcome_html)
        else:
            self.preview.load_html("<h1 align='center'>MADDDOG</h1>")

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open File", command=self.open_file)
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_command(label="Reset Editor", command=self.reset_editor)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        run_menu = tk.Menu(menubar, tearoff=0)
        run_menu.add_command(label="llama-3.3-70b-versatile", command=lambda: self.switch_model("llama-3.3-70b-versatile"))
        run_menu.add_command(label="llama-3.1-8b-instant", command=lambda: self.switch_model("llama-3.1-8b-instant"))
        run_menu.add_command(label="Gemini", command=lambda: self.switch_model("Gemini"))

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="README", command=self.load_readme)
        help_menu.add_command(label="About", command=self.show_about)

        menubar.add_cascade(label="File", menu=file_menu)
        menubar.add_cascade(label="Run model", menu=run_menu)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def render_markdown(self):
        source = self.response_area if self.active_model else self.editor
        raw_text = "\n" + source.get("1.0", tk.END).strip() + "\n"
        
        if not raw_text.strip() and not self.active_model:
            self.display_welcome_logo()
            return

        markdown_extras = [
            'fenced-code-blocks', 
            'tables', 
            'strike', 
            'footnotes', 
            'def_list', 
            'abbr'
        ]

        # Convert Markdown to HTML
        html_body = markdown2.markdown(raw_text, extras=markdown_extras)
        
        # FIX: Ensure tables render structural boundaries cleanly without CSS injection 
        html_body = html_body.replace("<table>", '<table border="1" cellpadding="5" cellspacing="0" width="100%">')
        html_body = html_body.replace("<thead>", '<thead bgcolor="#f2f2f2">')
        
        # Native Super/Subscript regex conversions bypassing CSS
        import re
        html_body = re.sub(r'\^([^\^]+)\^', r'<sup>\1</sup>', html_body)
        html_body = re.sub(r'~([^~<>\s]+)~', r'<sub>\1</sub>', html_body)

        # Native HTML Hex Entity Emoji Map for cross-platform rendering
        emoji_map = {
            ":smile:": "&#x1F604;", ":smiley:": "&#x1F603;", ":joy:": "&#x1F602;", ":laughing:": "&#x1F606;", 
            ":blush:": "&#x1F60A;", ":wink:": "&#x1F609;", ":heart_eyes:": "&#x1F60D;", ":kissing_heart:": "&#x1F618;",
            ":thumbsup:": "&#x1F44D;", ":thumbsdown:": "&#x1F44E;", ":heart:": "&#x2764;&#xFE0F;", ":broken_heart:": "&#x1F494;",
            ":star:": "&#x2B50;", ":fire:": "&#x1F525;", ":rocket:": "&#x1F680;", ":dog:": "&#x1F436;", 
            ":cat:": "&#x1F431;", ":tada:": "&#x1F389;", ":warning:": "&#x26A0;&#xFE0F;", ":check_mark:": "&#x2714;&#xFE0F;"
        }
        
        def emoji_replacer(match):
            shortcode = match.group(0)
            return emoji_map.get(shortcode, shortcode)
            
        html_body = re.sub(r':[a-zA-Z0-9_]+:', emoji_replacer, html_body)

        # Native standalone HTML structure with no CSS styling blocks
        styled_html = f"""<html>
        <body>
            {html_body}
        </body>
        </html>"""
        
        self.preview.load_html(styled_html)
        
        words = len(raw_text.split())
        self.status.config(text=f"Words: {words} | Mode: {self.active_model or 'Standard'}")

    def load_readme(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")
        if os.path.exists(path):
            self.load_file_from_path(path)
        else:
            messagebox.showinfo("MADDDOG", "README.md not found in the source directory.")

    def load_file_from_path(self, path):
        self.switch_model(None)
        self.current_path = path
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", content)
        self.is_modified = False
        self.editor.edit_modified(False)
        self.render_markdown()
        self.update_window_title()

    def update_window_title(self):
        display_name = os.path.basename(self.current_path) if self.current_path else self.app_name
        title = f"{display_name}"
        if self.is_modified: title += " [modified]"
        if self.active_model: title += f" (Mode: {self.active_model})"
        self.root.title(title)

    def switch_model(self, model_name):
        self.active_model = model_name
        self.response_area.delete("1.0", tk.END)
        if model_name:
            if self.btn_frame not in self.left_paned.panes():
                self.left_paned.add(self.btn_frame, height=50)
                self.left_paned.add(self.response_area, height=300)
        else:
            try:
                self.left_paned.forget(self.btn_frame)
                self.left_paned.forget(self.response_area)
            except: pass
        self.update_window_title()
        self.render_markdown()

    def run_ai_model(self):
        prompt = self.editor.get("1.0", tk.END).strip()
        if not prompt: return
        key_name = "GOOGLE_API_KEY" if self.active_model == "Gemini" else "GROQ_API_KEY"
        api_key = os.getenv(key_name)
        if not api_key:
            messagebox.showerror("Key Missing", f"Set {key_name} Environment Variable")
            return
        self.submit_btn.config(state=tk.DISABLED, text="Thinking...")
        threading.Thread(target=self.call_api_thread, args=(prompt, api_key), daemon=True).start()

    def call_api_thread(self, prompt, api_key):
        sys_msg = "You are a senior architect. Output clean Markdown only."
        try:
            if "llama" in str(self.active_model):
                m_id = self.active_model
                r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": m_id, "messages": [{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}]},
                    timeout=25)
                res = r.json()['choices'][0]['message']['content']
            else:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                r = requests.post(url, json={"contents": [{"parts": [{"text": f"{sys_msg}\n{prompt}"}]}]})
                res = r.json()['candidates'][0]['content']['parts'][0]['text']
            self.root.after(0, self.update_ai_ui, res)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.root.after(0, lambda: self.submit_btn.config(state=tk.NORMAL, text="⇧ Put your prompt here ⇧"))

    def update_ai_ui(self, text):
        self.response_area.delete("1.0", tk.END)
        self.response_area.insert("1.0", text)
        self.submit_btn.config(state=tk.NORMAL, text="⇧ Put your prompt here ⇧")
        self.render_markdown()

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("Markdown", "*.md"), ("Text", "*.txt")])
        if path:
            self.load_file_from_path(path)

    def save_file(self):
        if self.current_path:
            with open(self.current_path, 'w', encoding='utf-8') as f: f.write(self.editor.get("1.0", tk.END))
            self.is_modified = False
            self.update_window_title()
        else: self.save_file_as()

    def save_file_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".md")
        if path: self.current_path = path; self.save_file()

    def reset_editor(self):
        if messagebox.askyesno("Confirm", "Clear?"):
            self.switch_model(None)
            self.editor.delete("1.0", tk.END)
            self.is_modified = False
            self.current_path = None
            self.update_window_title()
            self.display_welcome_logo()

    def show_about(self):
        messagebox.showinfo("About", "MADDDOG Markdown Renderer\nVersion 2.6")

    def on_content_changed(self, event):
        # FIXED: Generic modification handler using event widget structure dynamically
        widget = event.widget
        if widget.edit_modified():
            if not self.is_modified:
                self.is_modified = True
                self.update_window_title()
            if self.debounce_timer: self.root.after_cancel(self.debounce_timer)
            self.debounce_timer = self.root.after(250, self.render_markdown)
            widget.edit_modified(False)

if __name__ == "__main__":
    root = tk.Tk()
    app = MarkdownExpertEditor(root)
    root.mainloop()
