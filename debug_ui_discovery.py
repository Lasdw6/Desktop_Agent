#!/usr/bin/env python3
"""
Debug script to understand why UI discovery isn't finding elements
"""

import sys
import traceback
sys.path.append('src-py')

try:
    import uiautomation as auto
    import time
    
    def debug_ui_discovery():
        print("🔍 Debug UI Discovery")
        print("=" * 40)
        
        try:
            # Get foreground window
            print("1. Getting foreground window...")
            foreground = auto.GetForegroundControl()
            if foreground:
                print(f"   ✅ Foreground: {foreground.Name} ({foreground.ControlTypeName})")
            else:
                print("   ❌ No foreground window found")
            
            # Get root (desktop)
            print("\n2. Getting desktop root...")
            root = auto.GetRootControl()
            if root:
                print(f"   ✅ Root: {root.Name} ({root.ControlTypeName})")
            else:
                print("   ❌ No root found")
                return
            
            # Try to find any children at all
            print("\n3. Looking for any child elements...")
            children = root.GetChildren()
            print(f"   Found {len(children)} top-level windows")
            
            # Look at first few windows
            for i, child in enumerate(children[:5]):
                try:
                    name = child.Name or "(no name)"
                    control_type = child.ControlTypeName
                    visible = not child.IsOffscreen
                    enabled = child.IsEnabled
                    print(f"   Window {i+1}: '{name}' ({control_type}) - Visible: {visible}, Enabled: {enabled}")
                    
                    # Look for elements in this window
                    if visible and enabled and name.strip():
                        window_children = child.GetChildren()
                        print(f"     └─ Has {len(window_children)} child elements")
                        
                        # Look at first few elements in this window
                        for j, elem in enumerate(window_children[:3]):
                            try:
                                elem_name = elem.Name or "(no name)"
                                elem_type = elem.ControlTypeName
                                elem_visible = not elem.IsOffscreen
                                elem_enabled = elem.IsEnabled
                                print(f"       Element {j+1}: '{elem_name}' ({elem_type}) - V:{elem_visible}, E:{elem_enabled}")
                            except:
                                print(f"       Element {j+1}: (error reading)")
                        
                except Exception as e:
                    print(f"   Window {i+1}: Error - {e}")
            
            # Try with a specific application
            print("\n4. Looking for common applications...")
            common_apps = ["notepad", "calculator", "explorer", "chrome", "firefox", "code"]
            
            for app_name in common_apps:
                try:
                    # Try to find window by name
                    windows = auto.FindAllByName(app_name)
                    if windows:
                        print(f"   ✅ Found {len(windows)} '{app_name}' windows")
                        for window in windows[:1]:  # Just check first one
                            if not window.IsOffscreen and window.IsEnabled:
                                window_children = window.GetChildren()
                                interactive_count = 0
                                for child in window_children:
                                    if child.IsEnabled and not child.IsOffscreen and child.Name.strip():
                                        if child.ControlTypeName in ['Button', 'Edit', 'ComboBox', 'CheckBox']:
                                            interactive_count += 1
                                print(f"     └─ Has {interactive_count} interactive elements")
                except:
                    pass
                    
        except Exception as e:
            print(f"❌ Debug failed: {e}")
            traceback.print_exc()

    def test_with_notepad():
        print("\n" + "=" * 40)
        print("🗒️  Testing with Notepad")
        print("=" * 40)
        
        import subprocess
        import time
        
        # Try to open notepad
        try:
            print("Opening Notepad...")
            subprocess.Popen(['notepad.exe'])
            time.sleep(2)  # Wait for it to open
            
            # Now try discovery
            print("Running discovery on Notepad...")
            from ui_element_discovery import UIElementDiscovery
            discovery = UIElementDiscovery()
            elements = discovery.discover_elements()
            
            if isinstance(elements, list):
                print(f"✅ Found {len(elements)} elements with Notepad open")
                for elem in elements[:5]:
                    print(f"   • {elem['control_type']}: '{elem['name']}'")
            else:
                print(f"❌ Error: {elements}")
                
        except Exception as e:
            print(f"❌ Notepad test failed: {e}")

    if __name__ == "__main__":
        debug_ui_discovery()
        
        response = input("\n🗒️  Open Notepad for testing? (y/n): ")
        if response.lower() == 'y':
            test_with_notepad()
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure uiautomation is installed: pip install uiautomation")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    traceback.print_exc() 