import os
import customtkinter as ctk
from tkinter import filedialog, messagebox

# Core integration with Rubin's backend package
try:
    from disassembly_loader import build_guide, DepthSpec, DepthMode, UnparsableModelError
except ImportError:
    build_guide = None
    DepthSpec = None
    DepthMode = None
    UnparsableModelError = Exception
    print("Warning: disassembly_loader package not found in the current directory.")


try:
    from word_exporter import export_to_word
except Exception as e:
    print(f"\n[!!! ERRORE REALE WORD !!!] {repr(e)}\n")
    export_to_word = None

try:
    from html_exporter import export_to_html
except Exception as e:
    print(f"\n[!!! ERRORE REALE HTML !!!] {repr(e)}\n")
    export_to_html = None

try:
    from pptx_exporter import export_to_pptx
except Exception as e:
    print(f"\n[!!! ERRORE REALE PPTX !!!] {repr(e)}\n")
    export_to_pptx = None
try:
    from md_exporter import export_to_md
except Exception as e:
    print(f"\n[!!! ERRORE REALE MD !!!] {repr(e)}\n")
    export_to_md = None

# Global UI Appearance Settings
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class EliteExporterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Disassembly Wizard - JSON Exporter")
        self.geometry("950x600")

        # State variables initialized directly within constructor block
        self.json_file_path = ctk.StringVar(value="")
        self.selected_format = "PDF"

        # Grid layout configuration for main window switching
        self.grid_columnconfigure(0, weight=1)  # Sidebar space
        self.grid_columnconfigure(1, weight=4)  # Main Content space
        self.grid_rowconfigure(0, weight=1)

        self.create_sidebar()
        self.create_main_content()

    def create_sidebar(self):
        """Constructs the left navigation sidebar for export formats."""
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(7, weight=1)  # Pushes theme switch to bottom

        sidebar_title = ctk.CTkLabel(self.sidebar, text="EXPORT FORMATS", font=ctk.CTkFont(size=14, weight="bold"))
        sidebar_title.grid(row=0, column=0, padx=20, pady=(30, 20))

        formats = [
            ("PDF (.pdf)", "PDF"),
            ("Text (.txt)", "TXT"),
            ("Markdown (.md)", "MD"),
            ("HTML + JS", "HTML+JS"),
            ("PowerPoint (.pptx)", "PPTX"),
            ("Word (.docx)", "DOCX")
        ]

        self.format_buttons = {}
        for idx, (text, fmt) in enumerate(formats):
            btn = ctk.CTkButton(
                self.sidebar,
                text=text,
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray70", "gray30"),
                anchor="w",
                command=lambda f=fmt: self.change_format(f)
            )
            btn.grid(row=idx + 1, column=0, padx=10, pady=5, sticky="ew")
            self.format_buttons[fmt] = btn

        # Theme toggle mechanism
        self.mode_switch = ctk.CTkSwitch(self.sidebar, text="Dark Mode", command=self.toggle_theme)
        self.mode_switch.grid(row=8, column=0, padx=20, pady=20, sticky="s")
        if ctk.get_appearance_mode() == "Dark":
            self.mode_switch.select()

    def create_main_content(self):
        """Constructs the primary configuration panel on the right."""
        self.content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.content_area.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(3, weight=1)  # Expandable validation log space

        self.main_title = ctk.CTkLabel(self.content_area, text="PDF Export Settings",
                                       font=ctk.CTkFont(size=22, weight="bold"))
        self.main_title.grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Section 1: JSON File Uploader Container
        self.file_frame = ctk.CTkFrame(self.content_area)
        self.file_frame.grid(row=1, column=0, sticky="ew", pady=10, padx=5)
        self.file_frame.grid_columnconfigure(0, weight=1)

        file_title = ctk.CTkLabel(self.file_frame, text="Source Model (JSON)", font=ctk.CTkFont(size=12, weight="bold"))
        file_title.grid(row=0, column=0, columnspan=2, padx=15, pady=(10, 0), sticky="w")

        self.file_entry = ctk.CTkEntry(self.file_frame, textvariable=self.json_file_path,
                                       placeholder_text="No JSON file selected...")
        self.file_entry.grid(row=1, column=0, padx=15, pady=15, sticky="ew")

        self.upload_btn = ctk.CTkButton(self.file_frame, text="Browse File", width=100, command=self.browse_json)
        self.upload_btn.grid(row=1, column=1, padx=(0, 15), pady=15)

        # Section 2: Rubin's Loader Parameters (Depth Spec & BoM Toggle)
        self.options_frame = ctk.CTkFrame(self.content_area)
        self.options_frame.grid(row=2, column=0, sticky="ew", pady=10, padx=5)
        self.options_frame.grid_columnconfigure(1, weight=1)

        options_title = ctk.CTkLabel(self.options_frame, text="Loader Configuration",
                                     font=ctk.CTkFont(size=12, weight="bold"))
        options_title.grid(row=0, column=0, columnspan=2, padx=15, pady=(10, 0), sticky="w")

        ctk.CTkLabel(self.options_frame, text="Disassembly Depth:").grid(row=1, column=0, padx=15, pady=15, sticky="w")
        
        # Tendina semplificata per smontaggio ragionevole
        self.depth_dropdown = ctk.CTkOptionMenu(
            self.options_frame,
            values=["Full", "1 Livello", "2 Livelli", "3 Livelli", "4 Livelli"]
        )
        self.depth_dropdown.grid(row=1, column=1, padx=15, pady=15, sticky="w")

        # Il toggle della BoM scala direttamente alla riga 2 (abbiamo rimosso gli ID)
        self.bom_switch = ctk.CTkSwitch(self.options_frame, text="Include Bill of Materials (BoM)")
        self.bom_switch.grid(row=2, column=0, columnspan=2, padx=15, pady=(0, 15), sticky="w")

        # Section 3: Validation and Warnings Real-time Terminal Display
        self.log_frame = ctk.CTkFrame(self.content_area)
        self.log_frame.grid(row=3, column=0, sticky="nsew", pady=10, padx=5)
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(1, weight=1)

        log_title = ctk.CTkLabel(self.log_frame, text="Parser Validation & Output Logs",
                                 font=ctk.CTkFont(size=12, weight="bold"))
        log_title.grid(row=0, column=0, padx=15, pady=(10, 0), sticky="w")

        self.log_textbox = ctk.CTkTextbox(self.log_frame, font=ctk.CTkFont(family="Courier", size=12))
        self.log_textbox.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.log_write("System status: Ready. Please select a disassembly graph model.")

        # Section 4: Main Execution Controller Button
        self.export_btn = ctk.CTkButton(self.content_area, text="RUN EXPORT", font=ctk.CTkFont(size=14, weight="bold"),
                                        height=45, command=self.execute_export)
        self.export_btn.grid(row=4, column=0, pady=(20, 0))

        self.change_format("PDF")

    # --- Event Handlers and Integration Logic ---

    def browse_json(self):
        """Invokes native file dialog to map target file path."""
        file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if file_path:
            self.json_file_path.set(file_path)
            self.log_write(f"Target model bound: {os.path.basename(file_path)}")
            
            # --- Calcolo dinamico dei livelli ---
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Cerca di scoprire la profondità massima dal JSON
                max_depth = 1
                
                # IPOTESI 1: Il JSON ha un array "nodes" e ogni nodo ha una chiave "level"
                if "nodes" in data:
                    for node in data["nodes"]:
                        if "level" in node and isinstance(node["level"], int):
                            if node["level"] > max_depth:
                                max_depth = node["level"]
                
                # Se max_depth è rimasto 1, significa che il JSON non ha la parola "level" scritta così.
                # In quel caso metto un default di emergenza.
                if max_depth == 1:
                    max_depth = 4 # Default se non trova i livelli
                
                # Genera i valori dinamici per la tendina
                nuovi_valori = [f"Full ({max_depth})"]
                for i in range(1, max_depth):
                    label = "1 Livello" if i == 1 else f"{i} Livelli"
                    nuovi_valori.append(label)
                
                # Aggiorna la tendina nell'interfaccia
                self.depth_dropdown.configure(values=nuovi_valori)
                self.depth_dropdown.set(nuovi_valori[0])  # Seleziona 'Full' di default
                self.log_write(f"Graph max depth detected: {max_depth} levels.")

            except Exception as e:
                self.log_write(f"[AVVISO] Impossibile calcolare i livelli in automatico dal JSON: {e}")
                self.depth_dropdown.configure(values=["Full", "1 Livello", "2 Livelli", "3 Livelli"])
                self.depth_dropdown.set("Full")

    

    def change_format(self, fmt):
        """Updates internal routing context state and state visual cues."""
        self.selected_format = fmt
        self.main_title.configure(text=f"{fmt} Export Settings")

        for f, btn in self.format_buttons.items():
            if f == fmt:
                btn.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"], text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=("gray10", "gray90"))

    def toggle_theme(self):
        """Synchronizes window graphics theme with runtime switch stance."""
        if self.mode_switch.get() == 1:
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")

    def log_write(self, txt):
        """Appends runtime telemetry entries inside the log stream sub-view."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", txt + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def execute_export(self):
        """Processes options, evaluates graph using back-end modules, maps pipeline outputs."""
        path = self.json_file_path.get()
        if not path:
            messagebox.showwarning("Missing Context", "A target JSON graph file must be specified before execution.")
            return

        if not build_guide:
            self.log_write("[ERROR] Package 'disassembly_loader' cannot be resolved. Simulating layout behaviors...")
            messagebox.showinfo("Simulation Run", f"Mock execution triggered for format: {self.selected_format}")
            return

        # Evaluating dynamic DepthSpec strategies (Gestione ragionevole per livelli)
        depth_choice = self.depth_dropdown.get()
        
        # startswith("Full") capisce sia "Full" che "Full (3)" che "Full (4)"
        if depth_choice.startswith("Full"):
            spec = DepthSpec(mode=DepthMode.FULL)
        else:
            # Estrae solo il numero dalla stringa (es. prende '2' da '2 Livelli')
            livello_scelto = int(depth_choice.split()[0])
            
            # Assumo che aggiornerai il disassembly_loader aggiungendo DepthMode.LEVEL
            # Se nel loader hai chiamato i parametri diversamente, cambiali qui!
            try:
                spec = DepthSpec(mode=DepthMode.LEVEL, max_level=livello_scelto)
            except AttributeError:
                # Fallback temporaneo se non hai ancora aggiornato il loader
                self.log_write(f"[AVVISO] DepthMode.LEVEL non trovato nel loader. Fallback a KEEP_MAIN.")
                spec = DepthSpec(mode=DepthMode.KEEP_MAIN)

        bom_needed = self.bom_switch.get()

        # Orchestrating data across the architecture boundary
        try:
            self.log_write("\n--- Invoking Disassembly Loader Pipeline ---")
            guide = build_guide(path, depth=spec, include_bom=bom_needed)

            self.log_write(f"[SUCCESS] Context initialized for root target: '{guide.product.name}'")
            self.log_write(f"Total execution steps generated: {len(guide.steps)}")

            if guide.warnings:
                self.log_write(f"⚠️ Captured {len(guide.warnings)} non-blocking structure warnings:")
                for w in guide.warnings:
                    self.log_write(
                        f"  - [{w.severity.upper()}] Rule variant '{w.rule}': {w.message} (Target IDs: {w.node_ids})")
            else:
                self.log_write(" Validation assessment clear. Input architecture maps perfectly onto graph rules.")

            self.log_write(f"[ROUTING] Forwarding core model representation to Task Generator: {self.selected_format}")

            if self.selected_format == "DOCX":
                if export_to_word:
                    self.log_write("[PROCESS] Executing Simone's Word Export Module...")
                    # Passiamo depth=spec !
                    generated_path = export_to_word(path, depth=spec, include_bom=bom_needed)
                    self.log_write(f"[SUCCESS] Word Document created successfully at: {generated_path}")
                    messagebox.showinfo("Operation Succeeded", f"Word (.docx) file generated successfully!\n\nPath:\n{generated_path}")
                else:
                    self.log_write("[ERROR] 'word_exporter.py' module could not be loaded.")
                    messagebox.showerror("Export Failure", "The Word Exporter module is missing or contains errors.")

            elif self.selected_format == "HTML+JS":
                if export_to_html:
                    self.log_write("[PROCESS] Executing Lin's Interactive HTML Export Module...")
                    generated_path = export_to_html(path, depth=spec, include_bom=bom_needed)
                    self.log_write(f"[SUCCESS] Interactive HTML Guide created successfully at: {generated_path}")
                    messagebox.showinfo("Operation Succeeded", f"Interactive HTML guide generated successfully!\n\nPath:\n{generated_path}")
                else:
                    self.log_write("[ERROR] 'html_exporter.py' module could not be loaded.")
                    messagebox.showerror("Export Failure", "The HTML Exporter module is missing or contains errors.")

            elif self.selected_format == "PPTX":
                if export_to_pptx:
                    self.log_write("[PROCESS] Executing Ibrahim's PowerPoint Export Module...")
                    generated_path = export_to_pptx(path, depth=spec, include_bom=bom_needed)
                    self.log_write(f"[SUCCESS] PowerPoint Presentation created successfully at: {generated_path}")
                    messagebox.showinfo("Operation Succeeded", f"PowerPoint (.pptx) presentation generated successfully!\n\nPath:\n{generated_path}")
                else:
                    self.log_write("[ERROR] 'pptx_exporter.py' module could not be loaded.")
                    messagebox.showerror("Export Failure", "The PowerPoint Exporter module is missing or contains errors.")

            elif self.selected_format == "MD":
                if export_to_md:
                    self.log_write("[PROCESS] Executing Markdown Export Module...")
                    generated_path = export_to_md(path, depth=spec, include_bom=bom_needed)
                    self.log_write(f"[SUCCESS] Markdown Document created successfully at: {generated_path}")
                    messagebox.showinfo("Operation Succeeded", f"Markdown (.md) file generated successfully!\n\nPath:\n{generated_path}")
                else:
                    self.log_write("[ERROR] 'md_exporter.py' module could not be loaded.")
                    messagebox.showerror("Export Failure", "The Markdown Exporter module is missing or contains errors.")

        except UnparsableModelError as e:
            self.log_write(f"[PARSING REFUSED] Corrupted or invalid structural data format:\n{str(e)}")
            messagebox.showerror("Parsing Failure", f"The pipeline rejected the structural design rules:\n\n{str(e)}")
        except Exception as e:
            self.log_write(f"[SYSTEM FAILURE] Unexpected routing exception:\n{str(e)}")
            messagebox.showerror("System Failure Exception", f"An unhandled operational error occurred:\n{str(e)}")


if __name__ == "__main__":
    app = EliteExporterApp()
    app.mainloop()