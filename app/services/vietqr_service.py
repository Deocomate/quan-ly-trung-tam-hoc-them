import re
import unicodedata
import urllib.parse

def remove_vietnamese_accents(value: str) -> str:
    if not value:
        return ""
    # Normalize unicode to separate characters from diacritics
    value = unicodedata.normalize("NFD", value)
    # Filter out diacritics
    value = "".join([c for c in value if unicodedata.category(c) != "Mn"])
    # Replace special cases like Đ and đ
    return value.replace("đ", "d").replace("Đ", "D")

def normalize_transfer_content(value: str, max_length: int = 50) -> str:
    if not value:
        return ""
    value = remove_vietnamese_accents(value)
    # Replace non-alphanumeric characters with spaces
    value = re.sub(r'[^a-zA-Z0-9 ]', ' ', value)
    # Collapse multiple spaces into one, trim, and uppercase
    value = re.sub(r'\s+', ' ', value).strip().upper()
    return value[:max_length]

def normalize_account_name(value: str) -> str:
    if not value:
        return ""
    value = remove_vietnamese_accents(value)
    # Replace non-alphanumeric characters with spaces
    value = re.sub(r'[^a-zA-Z0-9 ]', ' ', value)
    # Collapse multiple spaces into one, trim, and uppercase
    value = re.sub(r'\s+', ' ', value).strip().upper()
    return value[:50]

def generate_vietqr_url(
    bank_id: str,
    account_no: str,
    account_name: str,
    amount: int,
    transfer_code: str,
    template: str = "compact2"
) -> str:
    bank_id = bank_id.strip() if bank_id else ""
    account_no = account_no.strip() if account_no else ""
    
    if not bank_id or not account_no:
        return ""
        
    base_url = f"https://img.vietqr.io/image/{bank_id}-{account_no}-{template}.png"
    params = {}
    
    if amount > 0:
        params["amount"] = str(amount)
        
    norm_code = normalize_transfer_content(transfer_code)
    if norm_code:
        params["addInfo"] = norm_code
        
    norm_name = normalize_account_name(account_name)
    if norm_name:
        params["accountName"] = norm_name
        
    if params:
        return f"{base_url}?{urllib.parse.urlencode(params)}"
    return base_url
