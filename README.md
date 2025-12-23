# Mall Parking Billing System

This project is a fully automated billing system for a mall parking lot. It handles vehicle entry and exit, calculates parking fees, and generates a printable receipt with a QR code for payment.

## Features

- **Automated Vehicle Recognition:** Scans vehicle number plates upon entry and exit.
- **Time Tracking:** Records the entry and exit times for each vehicle.
- **Fee Calculation:** Automatically calculates parking fees based on the duration of the stay.
- **Receipt Generation:** Creates a printable receipt for the customer.
- **QR Code Payment:** Includes a QR code on the receipt for easy, contactless payment.
- **GUI:** A simple graphical user interface to display information.

## Technology Stack

- **Backend:** Python
- **GUI:** Tkinter (or another library like PyQt)
- **QR Code:** `qrcode` library
- **Database:** SQLite
- **Image Processing (for future development):** OpenCV, Pytesseract
