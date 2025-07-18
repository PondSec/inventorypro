# Inventory Pro 🖥️📊

**A modern, web-based inventory management system** for tracking IT assets, devices, and components with advanced analytics.

## 🌟 Features

- **Multi-Category Tracking** (Hardware, Software, Peripherals)
- **Custom Field Definitions** per category (text, numbers, dropdowns)
- **Barcode/QR Support** for quick scanning
- **Status Monitoring** (In Use, In Stock, Defective)
- **Advanced Reporting** with visual charts
- **Role-Based Access Control** (Admin, Technician, Viewer)
- **RESTful API** for integrations
- **Responsive Design** works on desktop & mobile

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- SQLite (included) / PostgreSQL (recommended for production)
- Node.js 18+ (for frontend)

### Installation
```bash
# Clone repository
git clone https://github.com/yourusername/inventory-pro.git
cd inventory-pro

# Backend setup
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -r requirements.txt

# Frontend setup
cd frontend
npm install
npm run build

# Run (development mode)
flask run --debug