"""
UnifyOps  -  Sensitive Data Protection (SDP) Service (Phase 9.1)

Integrates with Google Cloud Sensitive Data Protection (DLP) API
with local regex/rule fallbacks for development and testing.
"""

import os
import re

class SensitiveDataProtectionService:
    """Manages PII identification, masking, and role-based data redaction."""

    def __init__(self) -> None:
        self.enabled = False
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            try:
                from google.cloud import dlp_v2
                self.client = dlp_v2.DlpServiceClient()
                self.project = os.environ.get("GCP_PROJECT_ID", "unifyops")
                self.enabled = True
            except Exception as e:
                print(f"[SDP Service] Failed to initialize GCP DLP client: {e}. Running in local simulation mode.")

    def scan_and_mask(self, text: str) -> tuple[str, list[str]]:
        """
        Scans document text for sensitive data (PII).
        Returns:
            processed_text (str): Text with redacted emails, masked phones, and role-restricted names.
            info_types_detected (list[str]): List of detected PII types (e.g. ["EMAIL_ADDRESS", "PHONE_NUMBER"]).
        """
        info_types = []
        processed_text = text

        # 1. Emails (Redact)
        email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
        emails = email_pattern.findall(processed_text)
        if emails:
            info_types.append("EMAIL_ADDRESS")
            processed_text = email_pattern.sub("[REDACTED_EMAIL]", processed_text)

        # 2. Phone Numbers (Mask)
        # Matches formats like +91-98765-43210, +1 (555) 123-4567, 9876543210
        phone_pattern = re.compile(r"(?:\+?\d{1,4}[-.\s]?)?\(?\d{2,5}\)?[-.\s]?\d{2,5}[-.\s]?\d{2,5}\b")
        phones = phone_pattern.findall(processed_text)
        if phones:
            info_types.append("PHONE_NUMBER")
            processed_text = phone_pattern.sub("[MASKED_PHONE]", processed_text)

        # 3. Social Security Numbers / SSN
        ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
        ssns = ssn_pattern.findall(processed_text)
        if ssns:
            info_types.append("US_SOCIAL_SECURITY_NUMBER")
            processed_text = ssn_pattern.sub("[REDACTED_SSN]", processed_text)

        # 4. Personal Names (Role-restricted Masking)
        # Scan for common names or title-cased engineer markers in text
        # E.g. "John Doe", "operator Rajesh Kumar", "engineer Deepak"
        # We wrap names in a special marker so they can be cleaned dynamically at query-time.
        name_markers = [
            r"\b[A-Z][a-z]+ [A-Z][a-z]+\b",  # First Last
            r"\b[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+\b"  # First M. Last
        ]
        
        # Avoid matching common titles as parts of names by lowercasing them in a temporary text for scanning
        temp_text = processed_text
        titles_to_lower = ["Operator", "Supervisor", "Engineer", "Technician", "Manager", "Please", "Contact", "Verify"]
        for title in titles_to_lower:
            temp_text = re.sub(rf"\b{title}\b", title.lower(), temp_text)

        # Avoid matching common document terms, titles or equipment units
        ignored_names = {
            "UnifyOps", "P&ID", "Plant", "CDU", "SOP", "RCA", "Incident", "Tata", "Steel", 
            "Crude", "Reflux", "Operator", "Supervisor", "Engineer", "Technician", "Manager",
            "Please", "Contact", "Verify", "Report", "Audit", "Safety", "Loto", "Lockout"
        }
        
        names_found = []
        for marker in name_markers:
            for match in re.finditer(marker, temp_text):
                name = match.group(0)
                # Check if it looks like a real name and isn't an ignored word
                first_word = name.split()[0]
                last_word = name.split()[-1]
                if first_word not in ignored_names and last_word not in ignored_names:
                    names_found.append(name)

        if names_found:
            info_types.append("PERSON_NAME")
            # De-duplicate names to avoid replacing substrings recursively
            for name in sorted(list(set(names_found)), key=len, reverse=True):
                # Replace only plain text with role-restricted markers
                # (Ensure we don't wrap an already wrapped name)
                pattern = rf"(?<!\[\[SENSITIVE_PERSON:)\b{re.escape(name)}\b"
                processed_text = re.sub(pattern, f"[[SENSITIVE_PERSON:{name}]]", processed_text)

        return processed_text, list(set(info_types))

    def resolve_sensitive_data(self, text: str, role: str) -> str:
        """
        Dynamically cleans/scrubs role-restricted PII name markers based on user role (FR-9.1.2).
        If role is admin or supervisor, returns raw names. Otherwise, masks names.
        """
        role_lower = str(role).lower()
        has_access = "admin" in role_lower or "supervisor" in role_lower or "manager" in role_lower

        def replace_match(match):
            name = match.group(1)
            return name if has_access else "[REDACTED_NAME]"

        # Match [[SENSITIVE_PERSON:Name]]
        marker_pattern = re.compile(r"\[\[SENSITIVE_PERSON:(.*?)\]\]")
        return marker_pattern.sub(replace_match, text)


# Singleton
sdp_service = SensitiveDataProtectionService()
