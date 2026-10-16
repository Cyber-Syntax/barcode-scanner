# PRD.md — Barcode Scanner Desktop App (MVP)

## 1. Overview

Build a lightweight Windows desktop application using Python that reads 1D barcodes from imported images and displays the decoded values.

The goal is to replace manual barcode-reading tools with a simple GUI that lets employees import an image, view all detected barcodes, and copy each result individually.

## 2. Goals

- Read 1D barcodes from image files.
- Detect multiple barcodes in a single image.
- Display each detected barcode's decoded value and barcode type.
- Provide a dedicated Copy button for each detected barcode.
- Keep the interface simple, fast, and easy for non-technical employees.

## 3. MVP Features

### 3.1 Image Import

- Provide an **Import Image** button.
- Support common image formats: PNG, JPG, JPEG, and BMP.
- Allow employees to select an image through the standard Windows file picker.
- Display a preview of the imported image.
- Allow employees to import another image without restarting the application.

### 3.2 Barcode Detection

- Use Python with `pyzbar` and the ZBar library to decode 1D barcodes.
- Detect all readable barcodes in the imported image.
- Return the decoded value and barcode symbology for each detection.
- Support common 1D formats, including EAN-13, EAN-8, UPC-A, UPC-E, Code 128, Code 39, and ITF, subject to decoder capabilities.
- Do not silently discard valid detections because multiple barcodes exist in the same image.

### 3.3 Results Display

Display each detected barcode as a separate result row or card containing:

- Barcode type (e.g., EAN-13 or Code 128).
- Decoded barcode value.
- A **Copy** button.

Example:

| Barcode type | Decoded value   | Action |
| ------------ | --------------- | ------ |
| EAN-13       | `5901234123457` | Copy   |
| Code 128     | `123456789012`  | Copy   |
| Code 39      | `ABC12345`      | Copy   |

The example values are illustrative.

Each Copy button must copy only its associated barcode value to the Windows clipboard. Display brief feedback after copying, such as "Copied!".

### 3.4 Empty and Error States

- If no barcode is detected, display: "No barcodes detected. Try another image."
- If an image cannot be opened, display a clear error message.
- If image decoding fails, allow the employee to retry with another image.
- Keep the application responsive and prevent crashes caused by invalid or unsupported images.

## 4. Basic User Workflow

1. Open the application.
2. Click **Import Image**.
3. Select a barcode image.
4. View the imported image and detected barcode results.
5. Click **Copy** next to the desired barcode.
6. Paste the value into the warehouse management system or another application.
7. Import the next image when ready.

## 5. UI Requirements

- Simple, clean Windows desktop interface.
- Image preview area.
- Clearly visible Import Image button.
- Results list supporting multiple barcode detections.
- Individual Copy button for every result.
- Clear loading, success, empty, and error states.
- Scrollable results area for images containing many barcodes.
- No unnecessary configuration screens or complex workflows.

## 6. Technical Requirements

- Language: Python.
- GUI: Tkinter for a lightweight implementation, or PySide if a richer interface is justified.
- Barcode decoding: `pyzbar` with ZBar.
- Image handling: Pillow.
- Clipboard: A reliable Windows-compatible clipboard implementation.
- Packaging: PyInstaller to produce a standalone Windows executable.

The barcode-decoding logic must be separated from the GUI so it can be tested independently and extended later.

## 7. Out of Scope for MVP

The following features are explicitly excluded from the first version:

- WhatsApp integration.
- Automatic customer-name detection.
- OCR or AI-based text recognition.
- Automatic selection of the correct barcode for the WMS.
- Direct WMS integration or automated data entry.
- Database or job-history management.
- User accounts and permissions.
- Cloud services or external APIs.
- Automatic folder monitoring.
- Batch processing of multiple image files.

## 8. Acceptance Criteria

The MVP is complete when:

1. An employee can import a supported image through the GUI.
2. The application detects multiple readable 1D barcodes in one image.
3. Every detected result displays its decoded value and barcode type.
4. Every result has an individual Copy button.
5. Copying a result places the exact decoded value on the clipboard.
6. The GUI handles images with no barcodes without crashing.
7. The GUI handles unreadable or invalid images with a clear error message.
8. The employee can import a new image and repeat the workflow without restarting the application.
9. The application can be packaged and launched as a Windows `.exe`.

## 9. Future Improvements

Potential follow-up features, after the MVP is validated:

- Barcode-region highlighting in the image preview.
- Image rotation and contrast enhancement for difficult images.
- Copy all detected values at once.
- Configurable barcode-type priorities.
- Customer-name association.
- Batch image processing.
- Processing history.
- WhatsApp intake automation.
- WMS desktop automation.

## 10. MVP Success Metric

The application reliably reads the barcodes that employees currently have to read manually and reduces the work to importing an image and clicking Copy next to the required result.

**Priority:** Correct decoding, reliable clipboard copying, and a simple user experience over additional features.
