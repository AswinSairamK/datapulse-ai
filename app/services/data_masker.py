# ============================================================
# data_masker.py — Data masking service
# ============================================================
# Applies masking to sensitive data before sending it to
# external services (AI) or displaying in the dashboard.
#
# Masking strategies:
# - email: keep domain, mask local part ("john@mail.com" → "****@mail.com")
# - phone: keep first 3 and last 2 digits ("1234567890" → "123*****90")
# - address: keep first word ("123 Main St, NYC" → "123 *** *** ***")
# - name: keep first letter ("John Smith" → "J*** S***")
# - credit_card: keep last 4 digits ("1234567812345678" → "************5678")
# - ssn: mask all except last 4 ("123-45-6789" → "***-**-6789")
# - full: mask entire value ("anything" → "********")
# - custom: user-defined visible_start and visible_end
# ============================================================

import re
from sqlalchemy.orm import Session
from app.models.models import MaskingRule


class DataMasker:
    """
    Applies masking rules to query results.
    Masks are applied to columns before data leaves the system.
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def get_masking_map(self, data_source_id: int, table_name: str) -> dict:
        """
        Get all active masking rules for a table as a dict.
        
        Returns:
            {
                "email": {"mask_type": "email", ...},
                "phone": {"mask_type": "phone", ...}
            }
        """
        rules = self.db.query(MaskingRule).filter(
            MaskingRule.data_source_id == data_source_id,
            MaskingRule.table_name == table_name,
            MaskingRule.is_active == True
        ).all()
        
        return {
            rule.column_name: {
                "mask_type": rule.mask_type,
                "visible_start": rule.visible_start,
                "visible_end": rule.visible_end,
            }
            for rule in rules
        }

    def mask_email(self, value: str) -> str:
        """
        Mask email: keep domain, hide local part.
        'sairam111297@gmail.com' → '************@gmail.com'
        """
        if not value or "@" not in str(value):
            return self.mask_full(value)
        
        parts = str(value).split("@", 1)
        local_part = parts[0]
        domain = parts[1]
        masked_local = "*" * len(local_part)
        return f"{masked_local}@{domain}"

    def mask_phone(self, value: str) -> str:
        """
        Mask phone: keep first 3 and last 2 digits.
        '1234567890' → '123*****90'
        """
        if not value:
            return ""
        
        # Extract only digits for processing
        value_str = str(value)
        digits_only = re.sub(r'\D', '', value_str)
        
        if len(digits_only) < 5:
            return "*" * len(value_str)
        
        # Keep first 3 and last 2
        first = digits_only[:3]
        last = digits_only[-2:]
        middle_length = len(digits_only) - 5
        
        return f"{first}{'*' * middle_length}{last}"

    def mask_address(self, value: str) -> str:
        """
        Mask address: keep first word (usually house number), mask rest.
        '123 Main Street, New York, NY 10001' → '123 **** ****, ****, ** *****'
        """
        if not value:
            return ""
        
        value_str = str(value)
        words = value_str.split()
        
        if len(words) == 0:
            return ""
        
        # Keep first word, mask the rest with same length
        masked_words = [words[0]]
        for word in words[1:]:
            # Preserve punctuation
            clean_word = re.sub(r'[^\w]', '', word)
            masked = "*" * len(clean_word)
            # Re-add any trailing punctuation
            punct = re.findall(r'[^\w]', word)
            if punct:
                masked += "".join(punct)
            masked_words.append(masked)
        
        return " ".join(masked_words)

    def mask_name(self, value: str) -> str:
        """
        Mask name: keep first letter of each word.
        'John Smith' → 'J*** S****'
        """
        if not value:
            return ""
        
        value_str = str(value)
        words = value_str.split()
        masked_words = []
        
        for word in words:
            if len(word) <= 1:
                masked_words.append(word)
            else:
                masked_words.append(word[0] + "*" * (len(word) - 1))
        
        return " ".join(masked_words)

    def mask_credit_card(self, value: str) -> str:
        """
        Mask credit card: keep last 4 digits only.
        '1234567812345678' → '************5678'
        """
        if not value:
            return ""
        
        value_str = str(value)
        digits_only = re.sub(r'\D', '', value_str)
        
        if len(digits_only) < 4:
            return "*" * len(value_str)
        
        return "*" * (len(digits_only) - 4) + digits_only[-4:]

    def mask_ssn(self, value: str) -> str:
        """
        Mask SSN: show only last 4 digits.
        '123-45-6789' → '***-**-6789'
        """
        if not value:
            return ""
        
        value_str = str(value)
        if len(value_str) <= 4:
            return "*" * len(value_str)
        
        return "*" * (len(value_str) - 4) + value_str[-4:]

    def mask_full(self, value) -> str:
        """
        Mask entire value.
        'anything' → '********'
        """
        if value is None:
            return None
        value_str = str(value)
        if not value_str:
            return ""
        return "*" * len(value_str)

    def mask_custom(self, value, visible_start: int, visible_end: int) -> str:
        """
        Custom mask: show N characters at start and M at end.
        """
        if not value:
            return ""
        
        value_str = str(value)
        if len(value_str) <= visible_start + visible_end:
            return value_str  # Too short to mask meaningfully
        
        start = value_str[:visible_start]
        end = value_str[-visible_end:] if visible_end > 0 else ""
        middle = "*" * (len(value_str) - visible_start - visible_end)
        
        return f"{start}{middle}{end}"

    def apply_mask(self, value, mask_type: str, visible_start: int = 0, visible_end: int = 0):
        """
        Apply the appropriate mask based on mask_type.
        """
        if value is None:
            return None
        
        mask_methods = {
            "email": self.mask_email,
            "phone": self.mask_phone,
            "address": self.mask_address,
            "name": self.mask_name,
            "credit_card": self.mask_credit_card,
            "ssn": self.mask_ssn,
            "full": self.mask_full,
        }
        
        if mask_type == "custom":
            return self.mask_custom(value, visible_start, visible_end)
        
        mask_fn = mask_methods.get(mask_type, self.mask_full)
        return mask_fn(value)

    def mask_query_result(self, data_source_id: int, table_name: str, columns: list, rows: list) -> list:
        """
        Apply masking rules to a query result.
        
        Takes the columns and rows returned from the database
        and applies masking to any columns that have rules.
        
        Returns the masked rows.
        """
        masking_map = self.get_masking_map(data_source_id, table_name)
        
        if not masking_map:
            return rows  # No masking rules, return as-is
        
        # Find which column indices need masking
        column_masks = {}
        for i, col_name in enumerate(columns):
            if col_name in masking_map:
                column_masks[i] = masking_map[col_name]
        
        if not column_masks:
            return rows
        
        # Apply masking to each row
        masked_rows = []
        for row in rows:
            masked_row = list(row)
            for col_idx, mask_info in column_masks.items():
                masked_row[col_idx] = self.apply_mask(
                    masked_row[col_idx],
                    mask_info["mask_type"],
                    mask_info["visible_start"],
                    mask_info["visible_end"]
                )
            masked_rows.append(masked_row)
        
        return masked_rows

    def mask_all_tables_result(self, data_source_id: int, columns: list, rows: list, table_hint: str = None) -> list:
        """
        Apply masking when we don't know exactly which table the data came from.
        Used for chat queries that might join tables.
        
        Matches column names against ALL masking rules for this data source.
        """
        # Get all masking rules for this data source
        rules = self.db.query(MaskingRule).filter(
            MaskingRule.data_source_id == data_source_id,
            MaskingRule.is_active == True
        ).all()
        
        if not rules:
            return rows
        
        # Build a map of column_name → mask_info
        # If same column exists in multiple tables, last one wins
        masking_map = {
            rule.column_name: {
                "mask_type": rule.mask_type,
                "visible_start": rule.visible_start,
                "visible_end": rule.visible_end,
            }
            for rule in rules
        }
        
        # Find columns to mask
        column_masks = {}
        for i, col_name in enumerate(columns):
            if col_name in masking_map:
                column_masks[i] = masking_map[col_name]
        
        if not column_masks:
            return rows
        
        masked_rows = []
        for row in rows:
            masked_row = list(row)
            for col_idx, mask_info in column_masks.items():
                masked_row[col_idx] = self.apply_mask(
                    masked_row[col_idx],
                    mask_info["mask_type"],
                    mask_info["visible_start"],
                    mask_info["visible_end"]
                )
            masked_rows.append(masked_row)
        
        return masked_rows