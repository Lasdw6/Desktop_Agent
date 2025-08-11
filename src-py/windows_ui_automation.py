"""
Windows UI Automation discovery utilities

Uses the `uiautomation` package (Microsoft UI Automation) to enumerate UI elements on Windows.
Safe to call from Flask handlers by using UIAutomationInitializerInThread to initialize COM in-thread.
"""

from typing import Any, Dict, List, Optional, Tuple
import ctypes

try:
    import uiautomation as auto
except Exception as e:  # pragma: no cover
    auto = None  # type: ignore


class WindowsElement:
    def __init__(self, element):
        self.element = element
        # Defensive attribute access; some providers may raise
        try:
            self.name = element.Name or ""
        except Exception:
            self.name = ""
        try:
            self.control_type = element.ControlTypeName or ""
        except Exception:
            self.control_type = ""
        try:
            self.automation_id = element.AutomationId or ""
        except Exception:
            self.automation_id = ""
        try:
            self.class_name = getattr(element, 'ClassName', '') or ""
        except Exception:
            self.class_name = ""
        try:
            rect = element.BoundingRectangle
            self.bounding_rect = {
                'left': rect.left,
                'top': rect.top,
                'right': rect.right,
                'bottom': rect.bottom,
                'width': max(0, rect.right - rect.left),
                'height': max(0, rect.bottom - rect.top),
                'center_x': (rect.left + rect.right) // 2,
                'center_y': (rect.top + rect.bottom) // 2,
            }
        except Exception:
            self.bounding_rect = {
                'left': 0, 'top': 0, 'right': 0, 'bottom': 0,
                'width': 0, 'height': 0, 'center_x': 0, 'center_y': 0,
            }
        try:
            self.is_enabled = bool(element.IsEnabled)
        except Exception:
            self.is_enabled = True
        try:
            self.is_visible = (element.IsOffscreen == False)
        except Exception:
            self.is_visible = True

    def is_clickable(self) -> bool:
        clickable_types = [
            'Button', 'Hyperlink', 'MenuItem', 'TabItem', 'ListItem',
            'CheckBox', 'RadioButton', 'Image', 'Text', 'Document', 'PaneControl'
        ]
        keywords = [
            'button', 'link', 'menu', 'tab', 'back', 'forward', 'search', 'submit', 'ok', 'cancel', 'open', 'save'
        ]
        name_lower = (self.name or '').lower()
        return (
            (self.control_type in clickable_types) or
            any(k in name_lower for k in keywords) or
            len(self.name.strip()) > 0
        ) and self._is_sized()

    def is_typable(self) -> bool:
        typable_types = ['Edit', 'Document', 'ComboBox']
        keywords = ['search', 'address', 'url', 'input', 'text', 'field', 'username', 'password', 'email']
        name_lower = (self.name or '').lower()
        return (
            (self.control_type in typable_types) or
            any(k in name_lower for k in keywords)
        ) and self._is_sized()

    def _is_sized(self) -> bool:
        try:
            return self.bounding_rect['width'] >= 8 and self.bounding_rect['height'] >= 8
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'control_type': self.control_type,
            'automation_id': self.automation_id,
            'class_name': self.class_name,
            'bounding_rect': self.bounding_rect,
            'is_enabled': self.is_enabled,
            'is_visible': self.is_visible,
            'clickable': self.is_clickable(),
            'typable': self.is_typable(),
        }


def _matches_app(element, app_filter: Optional[str]) -> bool:
    if not app_filter:
        return True
    filt = app_filter.lower()
    try:
        return (filt in (element.Name or "").lower()) or (filt in (getattr(element, 'ClassName', '') or '').lower())
    except Exception:
        return False


def _traverse_collect(element, depth: int, max_depth: int, app_filter: Optional[str], out: List[WindowsElement]):
    if depth > max_depth:
        return
    try:
        for child in element.GetChildren():
            try:
                if not _matches_app(child, app_filter):
                    # Still traverse in case descendants match
                    _traverse_collect(child, depth + 1, max_depth, app_filter, out)
                    continue
                w = WindowsElement(child)
                # Only keep visible/enabled-ish elements on the primary monitor
                if w.is_visible and w.is_enabled and (w.is_clickable() or w.is_typable()):
                    if _intersects_primary_monitor(w.bounding_rect):
                        out.append(w)
                _traverse_collect(child, depth + 1, max_depth, app_filter, out)
            except Exception:
                continue
    except Exception:
        pass


def discover_windows_elements(app_filter: Optional[str] = None, max_depth: int = 10) -> List[Dict[str, Any]]:
    """Discover interactive UI elements on Windows using UI Automation.

    Returns a list of dictionaries compatible with other discovery outputs.
    """
    if auto is None:
        return [{'error': 'uiautomation package not available'}]
    elements: List[WindowsElement] = []
    try:
        with auto.UIAutomationInitializerInThread():
            root = auto.GetRootControl()
            tmp: List[WindowsElement] = []
            _traverse_collect(root, 0, max_depth, app_filter, tmp)
            elements = tmp
    except Exception as e:
        return [{'error': f'Windows UI Automation failed: {e}'}]

    # Convert and sort by on-screen position
    result = [e.to_dict() for e in elements]
    result.sort(key=lambda x: (x['bounding_rect']['top'], x['bounding_rect']['left']))
    return result


def _get_primary_monitor_rect() -> Tuple[int, int, int, int]:
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    left = 0
    top = 0
    right = user32.GetSystemMetrics(0)
    bottom = user32.GetSystemMetrics(1)
    return left, top, right, bottom


def _intersects_primary_monitor(rect: Dict[str, int]) -> bool:
    try:
        l, t, r, b = rect.get('left', 0), rect.get('top', 0), rect.get('right', 0), rect.get('bottom', 0)
        pl, pt, pr, pb = _get_primary_monitor_rect()
        # No size or off-screen
        if r <= l or b <= t:
            return False
        # Intersection test
        inter_l = max(l, pl)
        inter_t = max(t, pt)
        inter_r = min(r, pr)
        inter_b = min(b, pb)
        return inter_r > inter_l and inter_b > inter_t
    except Exception:
        return True


def get_windows_actionable_summary(elements: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not elements or isinstance(elements, dict):
        return {'error': 'No elements to summarize', 'detection_method': 'Windows UI Automation'}
    clickable = [e for e in elements if e.get('clickable')]
    typable = [e for e in elements if e.get('typable')]
    def simplify(e: Dict[str, Any]) -> Dict[str, Any]:
        c = e['bounding_rect']
        return {
            'name': e['name'],
            'type': e['control_type'],
            'center': (c['center_x'], c['center_y']),
            'description': f"{e['control_type']}: '{e['name']}'",
            'class_name': e.get('class_name', ''),
            'automation_id': e.get('automation_id', ''),
        }
    return {
        'total_elements': len(elements),
        'clickable_count': len(clickable),
        'typable_count': len(typable),
        'clickable_elements': [simplify(e) for e in clickable[:10]],
        'typable_elements': [simplify(e) for e in typable[:5]],
        'detection_method': 'Windows UI Automation',
    }


def find_windows_element_by_description(description: str, elements: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not elements or isinstance(elements, dict):
        return None
    desc = (description or '').lower()
    # Exact name match
    for e in elements:
        if e.get('name', '').lower() == desc:
            return e
    # Partial match
    for e in elements:
        name = e.get('name', '').lower()
        if not name:
            continue
        if desc in name or name in desc:
            return e
    # Control type hint
    type_mappings = {
        'button': 'Button', 'input': 'Edit', 'textbox': 'Edit', 'text box': 'Edit',
        'dropdown': 'ComboBox', 'checkbox': 'CheckBox', 'radio': 'RadioButton', 'link': 'Hyperlink'
    }
    for k, t in type_mappings.items():
        if k in desc:
            matches = [e for e in elements if e.get('control_type') == t]
            if matches:
                return matches[0]
    return None


