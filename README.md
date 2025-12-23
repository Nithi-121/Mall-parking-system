**🅿️ Mall Parking Management System**

The Mall Parking Management System is a Python-based desktop application designed to automate and simplify vehicle parking operations in shopping malls and commercial complexes. It combines computer vision, cloud storage, and digital payments into a single efficient system.

📌 Features
🚗 Smart Entry & Exit Management

Manual vehicle number entry or automatic license plate detection

OCR powered by OpenCV and Tesseract

Reduces waiting time and human error

☁️ Cloud-Synced Database

Uses Supabase (PostgreSQL) for secure cloud storage

Real-time data synchronization

Access parking records, occupancy, and revenue remotely

💳 Automated Billing & Payments

Calculates parking charges based on duration

Generates detailed digital receipts

Creates dynamic UPI QR codes for cashless payments

⚡ High Performance

Multi-threaded architecture

Camera and OCR tasks run separately using a custom VisionHandler

Ensures smooth and responsive GUI

🛠️ Tech Stack

Language: Python 3.x

GUI: Tkinter (Themed UI)

Database: Supabase (Cloud PostgreSQL)

Computer Vision: OpenCV, Pytesseract

Other Tools: Threading, Python-dotenv

🧩 System Architecture

Desktop application with cloud backend

OCR module for number plate recognition

Secure environment variable handling

Modular and scalable design

🚀 Installation & Setup

Clone the repository:

git clone https://github.com/Nithi-121/mall-parking-management-system.git


Install required dependencies:

pip install -r requirements.txt


Configure environment variables using .env file:

Supabase URL

Supabase API Key

Run the application:

python main.py

📈 Future Enhancements

Admin dashboard with analytics

Mobile app integration

Automatic gate control

Advanced number plate recognition models

📄 License

This project is developed for educational and demonstration purposes.

👤 Author

Developed by Nithin
