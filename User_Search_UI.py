import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time

# --- IMPORT YOUR EXISTING FUNCTIONS ---
from embedding_documents import create_embeddings_db
from querry_documents import search_local_docs


# ============================================================
# Main App Controller
# ============================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Local Document Search")
        self.geometry("800x600")

        self.selected_folder = None
        self.num_results = 5

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        self.frames = {}

        for Page in (FolderSelectPage, SearchPage):
            frame = Page(parent=container, controller=self)
            self.frames[Page.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("FolderSelectPage")

    def show_frame(self, page_name):
        self.frames[page_name].tkraise()


# ============================================================
# Page 1 — Folder Selection Page
# ============================================================
class FolderSelectPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        ttk.Label(self, text="Please Select a Folder With\nThe Files You Would Like to View",
                  font=("Arial", 18)).pack(pady=20)

        ttk.Label(self, text="Note: Only .pdf, .doc, .docx files will be processed.",
                  font=("Arial", 12)).pack(pady=10)

        # --- Load folders from Downloads ---
        self.downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")

        # --- Filter folders by valid docs ---
        def folder_has_valid_docs(folder_path):
            try:
                files = os.listdir(folder_path)
                files = sorted(files, key=lambda f: os.path.getmtime(os.path.join(folder_path, f)), reverse=True)
                latest = files[:15]
                valid_exts = (".pdf", ".docx", ".doc")
                return any(f.lower().endswith(valid_exts) for f in latest)
            except:
                return False

        self.all_folders = [
            f for f in os.listdir(self.downloads_path)
            if os.path.isdir(os.path.join(self.downloads_path, f))
            and folder_has_valid_docs(os.path.join(self.downloads_path, f))
        ]

        # --- Filter Typebox ---
        ttk.Label(self, text="Filter Folders:", font=("Arial", 12)).pack(pady=5)
        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(self, textvariable=self.filter_var, width=40)
        filter_entry.pack()
        filter_entry.bind("<KeyRelease>", self.update_dropdown)

        # --- Dropdown ---
        self.folder_var = tk.StringVar()
        self.folder_dropdown = ttk.Combobox(
            self,
            textvariable=self.folder_var,
            values=self.all_folders,
            state="readonly",
            width=40
        )
        self.folder_dropdown.pack(pady=10)

        ttk.Button(self, text="Select Folder", command=self.select_folder).pack(pady=10)
        ttk.Button(self, text="Continue to Search Page",
                   command=self.continue_to_search).pack(pady=20)

    # ---------------------------------------------------------
    # Update dropdown based on filter text
    # ---------------------------------------------------------
    def update_dropdown(self, event=None):
        typed = self.filter_var.get().lower()

        if typed.strip() == "":
            filtered = self.all_folders
        else:
            filtered = [f for f in self.all_folders if typed in f.lower()]

        self.folder_dropdown["values"] = filtered

        # If the current selection no longer matches, clear it
        if self.folder_var.get() not in filtered:
            self.folder_var.set("")

    # ---------------------------------------------------------
    def select_folder(self):
        selected = self.folder_var.get()

        if not selected:
            messagebox.showerror("Error", "Please select a folder first.")
            return

        full_path = os.path.join(self.downloads_path, selected)
        self.controller.selected_folder = full_path
        messagebox.showinfo("Folder Selected", f"Selected: {full_path}")

    # ---------------------------------------------------------
    def continue_to_search(self):
        if not self.controller.selected_folder:
            messagebox.showerror("Error", "Please select a folder before continuing.")
            return

        try:
            if not self.controller.selected_folder:
                messagebox.showerror("Error", "Please select a folder before continuing.")
                return

            # Create popup window
            self.progress_win = tk.Toplevel(self)
            self.progress_win.title("Indexing Documents")
            self.progress_win.geometry("400x150")

            ttk.Label(self.progress_win, text="Indexing documents...", font=("Arial", 14)).pack(pady=10)

            self.progress_bar = ttk.Progressbar(self.progress_win, orient="horizontal",
                                                length=300, mode="determinate", maximum=100)
            self.progress_bar.pack(pady=10)

            ttk.Label(self.progress_win, text="This may take a moment.").pack()

            indexing_thread = threading.Thread(target=self.run_indexing)
            indexing_thread.start() # Keeps UI thread from blocking. UI thread does not FREEZE waiting for create_embeddings_db to finish before executing its next UI updates.
                                    # Instead, it keeps running as create_embeddings_db does its thing, and it just listens for it in the meantime to change its progress bar.

        except Exception as e:
            messagebox.showerror("Error", f"Embedding creation failed:\n{e}")
            return

    def run_indexing(self):
        def progress_callback(current, total):
            percent = int((current / total) * 100)
            self.progress_bar.after(0, lambda: self.progress_bar.config(value=percent))

        # Pass the selected folder and the progress_callback function directly into your create_embeddings_db function
        create_embeddings_db(self.controller.selected_folder, progress_callback)

        self.progress_win.destroy()
        self.controller.show_frame("SearchPage")



# ============================================================
# Page 2 — Search Page
# ============================================================
class SearchPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # --- Main layout: two columns ---
        self.columnconfigure(0, weight=0)   # Left controls
        self.columnconfigure(1, weight=1)   # Right results

        # ============================================================
        # LEFT SIDE CONTROLS
        # ============================================================
        left_frame = ttk.Frame(self)
        left_frame.grid(row=0, column=0, sticky="ns", padx=20, pady=20)

        ttk.Label(left_frame, text="Search Your Documents", font=("Arial", 18)).pack(pady=20)

        ttk.Label(left_frame, text="Number of Results:", font=("Arial", 12)).pack()
        self.slider_label = ttk.Label(left_frame, text="5 results")
        self.slider = ttk.Scale(left_frame, from_=5, to=20, orient="horizontal",
                                command=self.update_slider)
        self.slider.pack(pady=10)
        self.slider.set(5)

        self.slider_label.pack()

        ttk.Label(left_frame, text="Enter Search Query:", font=("Arial", 12)).pack(pady=10)
        self.query_var = tk.StringVar()
        ttk.Entry(left_frame, textvariable=self.query_var, width=40).pack()

        ttk.Button(left_frame, text="Search", command=self.run_search).pack(pady=20)
        ttk.Button(left_frame, text="Back to Folder Selection", command=self.backToFolders).pack(pady=20)

        # ============================================================
        # RIGHT SIDE SCROLLABLE RESULTS WINDOW (VERT + HORIZ)
        # ============================================================
        right_frame = ttk.Frame(self)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)

        # Canvas + scrollbars
        self.canvas = tk.Canvas(right_frame)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar_y = ttk.Scrollbar(right_frame, orient="vertical", command=self.canvas.yview)
        scrollbar_y.grid(row=0, column=1, sticky="ns")

        scrollbar_x = ttk.Scrollbar(right_frame, orient="horizontal", command=self.canvas.xview)
        scrollbar_x.grid(row=1, column=0, sticky="ew")

        self.canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        # Frame inside canvas
        self.results_frame = ttk.Frame(self.canvas)
        self.results_window = self.canvas.create_window((0, 0), window=self.results_frame, anchor="nw")

        # Resize scroll region whenever contents change
        def on_frame_configure(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        self.results_frame.bind("<Configure>", on_frame_configure)

    # ---------------------------------------------------------
    def backToFolders(self):
        self.controller.show_frame("FolderSelectPage")
    # ---------------------------------------------------------
    def update_slider(self, value):
        rounded = int(round(float(value) / 5) * 5)
        self.slider_label.config(text=f"{rounded} results")
        self.controller.num_results = rounded

    # ---------------------------------------------------------
    def run_search(self):
        query = self.query_var.get().strip()
        if not query:
            messagebox.showerror("Error", "Please enter a search query.")
            return

        # Clear previous results
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        try:
            results = search_local_docs(query, num_results=self.controller.num_results)
        except Exception as e:
            messagebox.showerror("Error", f"Search failed:\n{e}")
            return

        # Display results inside scrollable frame
        for idx, (content, source_file, location, distance) in enumerate(results, start=1):
            block = ttk.Frame(self.results_frame)
            block.pack(fill="x", pady=10, padx=10)

            ttk.Label(block, text=f"Rank #{idx}", font=("Arial", 14, "bold")).pack(anchor="w")
            ttk.Label(block, text=f"File: {source_file}").pack(anchor="w")
            ttk.Label(block, text=f"Location: {location}").pack(anchor="w")
            ttk.Label(block, text=f"Distance: {distance:.4f}").pack(anchor="w")

            # ============================================================
            # TEXT WIDGET (NO INNER SCROLLBARS, SCROLLS VIA OUTER CANVAS)
            # ============================================================
            text_widget = tk.Text(
                block,
                wrap="none",      # <-- allows horizontal scrolling via canvas
                height=10,
                width=100         # <-- make it wide so horizontal scroll is useful
            )
            text_widget.pack(fill="both", expand=True, pady=5)

            # Insert content
            text_widget.insert("1.0", content)

            # Configure highlight tag (bold + red)
            text_widget.tag_config("highlight", foreground="red", font=("Arial", 10, "bold"))

            # Highlight each query word
            query_words = self.query_var.get().strip().split()

            for word in query_words:
                if not word:
                    continue

                start = "1.0"
                while True:
                    pos = text_widget.search(word, start, stopindex="end", nocase=True)
                    if not pos:
                        break

                    end = f"{pos}+{len(word)}c"
                    text_widget.tag_add("highlight", pos, end)

                    start = end

            # Make text read-only
            text_widget.config(state="disabled")


# ============================================================
# Run App
# ============================================================
if __name__ == "__main__":
    app = App()
    app.mainloop()