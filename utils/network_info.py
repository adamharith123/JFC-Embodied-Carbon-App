"""
Network info helper — detects the host machine's local IP address
so other devices on the same network can find and connect to the app.
"""

import socket
import qrcode
import io


def get_local_ip():
    """
    Determine the local network IP of this machine.

    Uses a dummy socket connection (no actual data sent) to let the OS
    resolve which local interface/IP would be used to reach the network.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()

    return ip


def get_app_url(port=8501):
    ip = get_local_ip()
    return f"http://{ip}:{port}"


def generate_qr_code_bytes(url):
    """
    Generate a QR code image for the given URL, returned as PNG bytes
    suitable for st.image().
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()