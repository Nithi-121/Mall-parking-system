import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import datetime
import qrcode
from PIL import Image, ImageTk
import cv2
import re
import numpy as np
import io
import os
import threading
import queue
from contextlib import contextmanager

import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Try to import pytesseract
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
    # Default common paths for Tesseract on Windows
    possible_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        os.getenv('TESSERACT_CMD', '')
    ]
    
    tess_path = None
    for path in possible_paths:
        if path and os.path.exists(path):
            tess_path = path
            break
            
    if tess_path:
        pytesseract.pytesseract.tesseract_cmd = tess_path
    else:
        # Fallback or let it fail gracefully later if not found in PATH
        pass

except ImportError:
    TESSERACT_AVAILABLE = False
    pytesseract = None

class DatabaseManager:
    """Handles all Supabase database interactions."""
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Supabase URL and Key must be set in .env file")
        
        self.supabase: Client = create_client(url, key)

    def add_vehicle(self, vehicle_number):
        try:
            entry_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data = {"vehicle_number": vehicle_number, "entry_time": entry_time}
            response = self.supabase.table("vehicles").insert(data).execute()
            # Supabase-py v2 raises exception on error, checks aren't like requests
            return True, "Entry recorded successfully."
        except Exception as e:
            # Check for duplicate key error (usually contains policy or unique constraint info)
            err_str = str(e)
            if "duplicate key" in err_str or "23505" in err_str: 
                return False, f"Vehicle {vehicle_number} is already marked as parked."
            return False, f"Cloud Error: {err_str}"

    def get_vehicle_entry_time(self, vehicle_number):
        try:
            response = self.supabase.table("vehicles").select("entry_time").eq("vehicle_number", vehicle_number).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]['entry_time']
            return None
        except Exception as e:
            print(f"Fetch Error: {e}")
            return None

    def remove_vehicle(self, vehicle_number):
        try:
            response = self.supabase.table("vehicles").delete().eq("vehicle_number", vehicle_number).execute()
            # In Supabase, delete returns the deleted rows. If empty, maybe it wasn't there.
            if response.data and len(response.data) > 0:
                return True
            return False # Or True if 'not found' is considered success? User logic expects strict found.
        except Exception:
            return False

    def get_all_vehicles(self):
        try:
            # Assuming small dataset, just get all
            response = self.supabase.table("vehicles").select("*").order("entry_time", desc=True).execute()
            # Convert to list of tuples to match previous interface: (vehicle_number, entry_time)
            return [(row['vehicle_number'], row['entry_time']) for row in response.data]
        except Exception as e:
            print(f"List Error: {e}")
            return []

class VisionHandler:
    """Handles Camera and OCR operations in a separate thread."""
    def __init__(self, callback_func):
        self.callback = callback_func
        self.running = False
        self.thread = None

    def start_scan(self):
        if not TESSERACT_AVAILABLE:
            self.callback(False, "OCR library not found.")
            return
            
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.thread.start()

    def _scan_loop(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.callback(False, "Camera not accessible.")
            self.running = False
            return

        try:
            # We will use a flag to signal the UI thread that we are active
            # For this simple implementation, we'll keep the cv2 window logic 
            # but ensure it runs cleanly in this thread.
            
            while self.running:
                ret, frame = cap.read()
                if not ret: break
                
                h, w, _ = frame.shape
                cx, cy = w//2, h//2
                bw, bh = 300, 100
                cv2.rectangle(frame, (cx-bw//2, cy-bh//2), (cx+bw//2, cy+bh//2), (0, 255, 0), 2)
                cv2.putText(frame, "Fit Plate. SPACE: Capture, ESC: Exit", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                cv2.imshow('Scanner', frame)
                
                k = cv2.waitKey(1) & 0xFF
                if k == 27: # ESC
                    self.callback(False, "Scan cancelled.")
                    break
                elif k == 32: # SPACE
                    crop_img = frame[cy-bh//2:cy+bh//2, cx-bw//2:cx+bw//2]
                    gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
                    gray = cv2.bilateralFilter(gray, 11, 17, 17)
                    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    
                    config = '--oem 3 --psm 7'
                    text = pytesseract.image_to_string(thresh, config=config)
                    cleaned_text = re.sub(r'[^A-Z0-9]', '', text).strip()
                    
                    if len(cleaned_text) > 4:
                        self.callback(True, cleaned_text)
                        break
                    else:
                        print(f"Scan unclear: {text}")
                        # Optional: provide feedback on image
        finally:
            self.running = False
            cap.release()
            cv2.destroyAllWindows()

class ParkingSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("Mall Parking System")
        self.root.geometry("1100x700")
        
        self.db = DatabaseManager()
        self.vision = VisionHandler(self.on_scan_result)
        
        self.setup_styles()
        
        # Main Layout container
        self.main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left Panel (Controls)
        self.left_panel = ttk.Frame(self.main_container, padding="10")
        self.main_container.add(self.left_panel, weight=1)
        
        # Right Panel (Dashboard)
        self.right_panel = ttk.Frame(self.main_container, padding="10")
        self.main_container.add(self.right_panel, weight=2)
        
        self.create_left_panel()
        self.create_right_panel()
        
        # Status Bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.refresh_dashboard()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TLabel", font=("Segoe UI", 11))
        style.configure("TButton", font=("Segoe UI", 11, "bold"), padding=6)
        style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), foreground="#333")
        style.configure("SubHeader.TLabel", font=("Segoe UI", 14, "bold"), foreground="#555")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=25)

    def create_left_panel(self):
        ttk.Label(self.left_panel, text="Operations", style="Header.TLabel").pack(pady=(0, 20), anchor="w")
        
        # --- Entry Section ---
        entry_frame = ttk.LabelFrame(self.left_panel, text="Vehicle Entry", padding="15")
        entry_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(entry_frame, text="Vehicle Number:").pack(anchor="w")
        
        input_frame_entry = ttk.Frame(entry_frame)
        input_frame_entry.pack(fill=tk.X, pady=5)
        
        self.entry_vehicle_var = tk.StringVar()
        self.entry_input = ttk.Entry(input_frame_entry, textvariable=self.entry_vehicle_var, font=("Consolas", 14))
        self.entry_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        if TESSERACT_AVAILABLE:
            ttk.Button(input_frame_entry, text="📷", width=3, 
                       command=lambda: self.start_camera(self.entry_vehicle_var)).pack(side=tk.LEFT)
        
        ttk.Button(entry_frame, text="Record Entry", command=self.record_entry, cursor="hand2").pack(fill=tk.X, pady=(10, 0))

        # --- Exit Section ---
        exit_frame = ttk.LabelFrame(self.left_panel, text="Vehicle Exit", padding="15")
        exit_frame.pack(fill=tk.X)
        
        ttk.Label(exit_frame, text="Vehicle Number:").pack(anchor="w")
        
        input_frame_exit = ttk.Frame(exit_frame)
        input_frame_exit.pack(fill=tk.X, pady=5)
        
        self.exit_vehicle_var = tk.StringVar()
        self.exit_input = ttk.Entry(input_frame_exit, textvariable=self.exit_vehicle_var, font=("Consolas", 14))
        self.exit_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        if TESSERACT_AVAILABLE:
            ttk.Button(input_frame_exit, text="📷", width=3,
                       command=lambda: self.start_camera(self.exit_vehicle_var)).pack(side=tk.LEFT)
        
        ttk.Button(exit_frame, text="Process Exit & Payment", command=self.process_exit, cursor="hand2").pack(fill=tk.X, pady=(10, 0))

        if not TESSERACT_AVAILABLE:
            ttk.Label(self.left_panel, text="ℹ OCR unavailable.\nInstall Tesseract for camera features.", 
                      foreground="gray", font=("Segoe UI", 9)).pack(pady=20, anchor="w")

    def create_right_panel(self):
        ttk.Label(self.right_panel, text="Live Dashboard", style="Header.TLabel").pack(pady=(0, 10), anchor="w")
        
        stats_frame = ttk.Frame(self.right_panel)
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.occupancy_label = ttk.Label(stats_frame, text="Parked: 0", style="SubHeader.TLabel")
        self.occupancy_label.pack(side=tk.LEFT)
        
        ttk.Button(stats_frame, text="↻ Refresh", command=self.refresh_dashboard).pack(side=tk.RIGHT)

        columns = ("v_no", "entry_time", "duration")
        self.tree = ttk.Treeview(self.right_panel, columns=columns, show="headings")
        self.tree.heading("v_no", text="Vehicle No")
        self.tree.heading("entry_time", text="Entry Time")
        self.tree.heading("duration", text="Duration")
        
        self.tree.column("v_no", width=100)
        self.tree.column("entry_time", width=150)
        self.tree.column("duration", width=100)
        
        scrollbar = ttk.Scrollbar(self.right_panel, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree.bind("<Double-1>", self.on_tree_double_click)

    def on_tree_double_click(self, event):
        item = self.tree.selection()[0]
        vehicle_no = self.tree.item(item, "values")[0]
        self.exit_vehicle_var.set(vehicle_no)
        self.setStatus(f"Selected {vehicle_no} for exit.")

    def setStatus(self, message):
        self.status_var.set(message)
        self.root.after(4000, lambda: self.status_var.set("Ready"))

    def refresh_dashboard(self):
        # Clear current items
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        try:
            rows = self.db.get_all_vehicles()
            count = 0
            now = datetime.datetime.now()
            
            for row in rows:
                count += 1
                v_no, t_str = row
                try:
                    t_entry = datetime.datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S")
                    duration = now - t_entry
                    total_seconds = int(duration.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    dur_str = f"{hours}h {minutes}m"
                except ValueError:
                    dur_str = "Error"
                
                self.tree.insert("", "end", values=(v_no, t_str, dur_str))
                
            self.occupancy_label.config(text=f"Parked: {count}")
        except Exception as e:
            messagebox.showerror("DB Error", str(e))

    def record_entry(self):
        vehicle_number = self.entry_vehicle_var.get().strip().upper()
        if not vehicle_number:
            messagebox.showwarning("Input Error", "Please enter a vehicle number.")
            return

        success, msg = self.db.add_vehicle(vehicle_number)
        if success:
            self.setStatus(msg)
            self.entry_vehicle_var.set("")
            self.refresh_dashboard()
        else:
            if "already marked" in msg:
                messagebox.showerror("Error", msg)
            else:
                messagebox.showerror("Database Error", msg)

    def process_exit(self):
        vehicle_number = self.exit_vehicle_var.get().strip().upper()
        if not vehicle_number:
            messagebox.showwarning("Input Error", "Please enter a vehicle number.")
            return

        entry_time_str = self.db.get_vehicle_entry_time(vehicle_number)
        if not entry_time_str:
            messagebox.showerror("Not Found", f"Vehicle {vehicle_number} not found in records.")
            return

        # Calculate Fees
        try:
            entry_time = datetime.datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
            exit_time = datetime.datetime.now()
            duration = exit_time - entry_time
            duration_hours = duration.total_seconds() / 3600
            fee = round(duration_hours * 20, 2)
            if fee < 20: fee = 20.0
            
            # Remove from DB
            if self.db.remove_vehicle(vehicle_number):
                self.exit_vehicle_var.set("")
                self.refresh_dashboard()
                self.show_receipt_window(vehicle_number, entry_time, exit_time, duration, fee)
            else:
                messagebox.showerror("Error", "Failed to remove vehicle from database.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Processing error: {str(e)}")

    def start_camera(self, target_var):
        """Initiates the camera scan sequence."""
        self.current_target_var = target_var
        self.setStatus("Starting camera...")
        self.vision.start_scan()

    def on_scan_result(self, success, result):
        """Callback from VisionHandler (runs in thread, needs root.after for UI updates if strictly modifying UI, 
           but setting Var is usually thread-safe in Tkinter, though queue is better)."""
        # Proper way to update UI from thread
        self.root.after(0, lambda: self._handle_scan_result(success, result))

    def _handle_scan_result(self, success, result):
        if success:
            self.current_target_var.set(result)
            self.setStatus(f"Scanned: {result}")
        else:
            if "cancelled" not in result:
                self.setStatus(f"Scan failed: {result}")
            else:
                self.setStatus(result)

    def show_receipt_window(self, vehicle_number, entry_time, exit_time, duration, fee):
        receipt_window = tk.Toplevel(self.root)
        receipt_window.title("Payment Receipt")
        receipt_window.geometry("400x550")
        receipt_window.config(bg="white")
        
        frame = ttk.Frame(receipt_window, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="MALL PARKING RECEIPT", font=("Courier", 16, "bold")).pack(pady=10)
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        grid_frame = ttk.Frame(frame)
        grid_frame.pack(fill=tk.X, pady=10)
        
        details = [
            ("Vehicle No:", vehicle_number),
            ("Entry Time:", entry_time.strftime("%H:%M %d/%m")),
            ("Exit Time:", exit_time.strftime("%H:%M %d/%m")),
            ("Duration:", str(duration).split('.')[0]),
            ("Amount:", f"₹ {fee:.2f}")
        ]
        
        for i, (lbl, val) in enumerate(details):
            tk.Label(grid_frame, text=lbl, font=("Segoe UI", 10), bg="white", fg="#555").grid(row=i, column=0, sticky="w", pady=2)
            tk.Label(grid_frame, text=val, font=("Segoe UI", 10, "bold"), bg="white", fg="#000").grid(row=i, column=1, sticky="e", padx=20, pady=2)
            
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        
        tk.Label(frame, text=f"TOTAL PAYABLE: ₹ {fee:.2f}", font=("Segoe UI", 14, "bold"), bg="#f0f0f0", pady=10).pack(fill=tk.X)
        
        qr_img = self.generate_qr_image(vehicle_number, fee)
        if qr_img:
            qr_label = tk.Label(frame, image=qr_img, bg="white")
            qr_label.image = qr_img
            qr_label.pack(pady=15)
            
        tk.Label(frame, text="Scan to Pay via UPI", font=("Segoe UI", 9), bg="white", fg="gray").pack()
        
        ttk.Button(frame, text="Print / Close", command=receipt_window.destroy).pack(pady=20, fill=tk.X)

    def generate_qr_image(self, vehicle_number, fee):
        try:
            merchant_upi_id = "YOUR_UPI_ID@yourbank"
            merchant_name = "Mall Parking"
            note = f"Park fee {vehicle_number}"
            qr_data = f"upi://pay?pa={merchant_upi_id}&pn={merchant_name}&am={fee:.2f}&tn={note}"
            qr = qrcode.QRCode(box_size=8, border=2)
            qr.add_data(qr_data)
            qr.make(fit=True)
            pil_img = qr.make_image(fill_color="black", back_color="white")
            return ImageTk.PhotoImage(pil_img)
        except Exception as e:
            print(f"QR Gen Error: {e}")
            return None

if __name__ == "__main__":
    root = tk.Tk()
    app = ParkingSystem(root)
    root.mainloop()
