# ScreenEnv Migration Guide

This document outlines the migration from Windows UI Automation to ScreenEnv for cross-platform desktop automation.

## 🚀 Overview

The system has been migrated from Windows-specific UI Automation (`uiautomation`) to **ScreenEnv**, a Docker-based sandboxed desktop environment that enables cross-platform GUI automation.

### Key Benefits of ScreenEnv

- **Cross-platform**: Works on Windows, macOS, and Linux
- **Sandboxed**: Isolated Docker environment prevents interference
- **Reproducible**: Consistent behavior across different machines
- **Scalable**: Easy to deploy and manage multiple instances
- **Modern**: Based on Ubuntu desktop with modern applications

## 📋 Prerequisites

### 1. Docker Installation

**Windows:**

```bash
# Install Docker Desktop for Windows
# Download from: https://www.docker.com/products/docker-desktop/
```

**macOS:**

```bash
# Install Docker Desktop for Mac
# Download from: https://www.docker.com/products/docker-desktop/
```

**Linux:**

```bash
# Install Docker
sudo apt update
sudo apt install docker.io docker-compose
sudo usermod -aG docker $USER
# Log out and log back in for group changes to take effect
```

### 2. Python Dependencies

```bash
cd src-py
pip install -r requirements.txt
```

Key new dependencies:

- `screenenv`: Core sandboxed desktop automation
- `opencv-python`: Computer vision for UI element detection
- `numpy`: Array operations for image processing
- `docker`: Docker integration
- `smolagents`: Optional AI agent framework

## 🔧 Migration Changes

### Updated Files

1. **`src-py/requirements.txt`**

   - Removed: `uiautomation`
   - Added: `screenenv`, `opencv-python`, `numpy`, `docker`, `smolagents`

2. **`src-py/ui_element_discovery.py`**

   - Complete rewrite using ScreenEnv
   - Computer vision-based element detection
   - Cross-platform compatibility

3. **`src-py/main.py`**

   - Updated to use new ScreenEnv-based discovery
   - Added ScreenEnv test endpoints

4. **`test_screenenv_ui_bridge.py`**
   - New comprehensive test suite
   - Docker requirement validation
   - ScreenEnv functionality testing

## 🎯 New Architecture

### Before (Windows UI Automation)

```
Rust ──► Python ──► Windows UI Automation API ──► Native Windows Elements
```

### After (ScreenEnv)

```
Rust ──► Python ──► ScreenEnv (Docker) ──► Ubuntu Desktop ──► CV-based Detection
```

## 🛠️ Usage

### 1. Basic Setup Test

```bash
# Test ScreenEnv installation and Docker setup
python test_screenenv_ui_bridge.py
```

### 2. UI Element Discovery

```bash
# Discover all UI elements
python src-py/ui_element_discovery.py discover

# Get summary of interactive elements
python src-py/ui_element_discovery.py summary

# Find specific elements
python src-py/ui_element_discovery.py find "button"

# Test with specific application
python src-py/ui_element_discovery.py discover firefox
```

### 3. Test ScreenEnv Sandbox

```bash
# Test sandbox initialization
python src-py/ui_element_discovery.py test
```

### 4. Flask API Integration

```bash
# Start the Flask server
python src-py/main.py

# Test endpoints
curl http://localhost:5000/test-screenenv
curl http://localhost:5000/discover-ui-elements
curl http://localhost:5000/ui-summary
```

## 🔍 How It Works

### 1. Sandbox Creation

- ScreenEnv creates a Docker container with Ubuntu desktop
- Configurable resolution and display settings
- Isolated from host system

### 2. UI Element Detection

- Screenshots are captured from the sandboxed environment
- Computer vision algorithms detect UI elements:
  - Contour detection for buttons and controls
  - Size and position-based classification
  - Heuristic filtering for interactive elements

### 3. Element Classification

- **Buttons**: Small rectangular shapes (height < 30px, width > 50px)
- **Text Inputs**: Longer horizontal shapes (height < 25px, width > 100px)
- **Links**: Very small horizontal elements (height < 20px)
- **Panes**: Large rectangular areas (width > 200px, height > 100px)

### 4. Cross-Platform Compatibility

- Works on any system with Docker
- Consistent behavior across platforms
- No dependency on OS-specific APIs

## 📊 Feature Comparison

| Feature           | Windows UI Automation | ScreenEnv         |
| ----------------- | --------------------- | ----------------- |
| Platform Support  | Windows only          | Cross-platform    |
| Isolation         | None                  | Docker sandbox    |
| Element Detection | Native API            | Computer vision   |
| Reproducibility   | Variable              | Consistent        |
| Setup Complexity  | Low                   | Medium            |
| Reliability       | High (native)         | Medium (CV-based) |
| Performance       | Fast                  | Moderate          |
| Scalability       | Limited               | High              |

## 🚨 Known Limitations

### 1. Computer Vision Accuracy

- CV-based detection may miss some UI elements
- Less accurate than native API access
- May require tuning for specific applications

### 2. Performance

- Docker overhead adds latency
- Screenshot processing takes time
- Slower than native automation

### 3. Text Recognition

- Current implementation uses position-based naming
- Real OCR would improve element identification
- Consider adding `pytesseract` for better text extraction

## 🔬 Improvements and Extensions

### 1. Enhanced Element Detection

```python
# Add OCR for better text recognition
import pytesseract

def _extract_text_from_region(self, image, x, y, w, h):
    """Extract text using OCR"""
    roi = image[y:y+h, x:x+w]
    text = pytesseract.image_to_string(roi)
    return text.strip()
```

### 2. Machine Learning Integration

```python
# Use ML models for better UI element classification
import torch
from transformers import pipeline

def _classify_element_with_ml(self, image_region):
    """Classify UI element using ML model"""
    # Use pre-trained vision model for classification
    pass
```

### 3. Template Matching

```python
# Add template matching for common UI elements
import cv2

def _match_templates(self, image):
    """Match common UI element templates"""
    # Template matching for buttons, inputs, etc.
    pass
```

## 🧪 Testing

### Run All Tests

```bash
python test_screenenv_ui_bridge.py
```

### Individual Test Components

```bash
# Test Docker setup
python test_screenenv_ui_bridge.py test_docker_requirements

# Test ScreenEnv initialization
python test_screenenv_ui_bridge.py test_screenenv_initialization

# Test UI discovery
python test_screenenv_ui_bridge.py test_ui_discovery
```

## 📝 Migration Checklist

- [ ] Install Docker and verify it's running
- [ ] Update Python dependencies: `pip install -r src-py/requirements.txt`
- [ ] Test ScreenEnv setup: `python test_screenenv_ui_bridge.py`
- [ ] Verify UI element discovery works
- [ ] Test integration with Rust backend
- [ ] Update documentation and examples
- [ ] Performance testing and optimization
- [ ] Error handling and edge cases

## 🔗 Integration with Rust Backend

The Rust backend continues to work with the new Python scripts:

```rust
// Rust calls remain the same
fn call_python_ui_discovery(action: &str, args: &[&str]) -> Result<String, String> {
    // Execute Python script directly
    let mut cmd = Command::new("python");
    cmd.arg("../src-py/ui_element_discovery.py").arg(action);
    for arg in args {
        cmd.arg(arg);
    }
    // ... rest of implementation
}
```

The JSON interface remains compatible, ensuring seamless integration.

## 🎓 Next Steps

1. **Enhanced OCR**: Add `pytesseract` for better text recognition
2. **ML Integration**: Use vision models for better element classification
3. **Template Matching**: Add template matching for common UI patterns
4. **Performance Optimization**: Optimize CV processing and caching
5. **Error Resilience**: Improve error handling and recovery
6. **Extended Platform Support**: Test on more platforms and applications

## 💡 Tips for Success

1. **Start with Docker**: Ensure Docker is properly installed and running
2. **Test Incrementally**: Use the test scripts to validate each component
3. **Monitor Performance**: CV processing can be CPU-intensive
4. **Consider Caching**: Cache screenshots and element data when possible
5. **Fallback Strategies**: Always have coordinate-based fallbacks available

## 📞 Support

For issues with the migration:

1. Check Docker installation and daemon status
2. Verify Python dependencies are installed
3. Run the test script to identify specific issues
4. Check logs for detailed error messages
5. Consider fallback to coordinate-based automation when needed

The migration to ScreenEnv provides a solid foundation for cross-platform desktop automation while maintaining the existing API compatibility with the Rust backend.
