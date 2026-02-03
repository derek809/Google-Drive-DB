"""
Gemini Client for Mode 4
Wrapper for Google Gemini API - primarily for vision/image analysis.

Uses Gemini 2.0 Flash for cost-effective, fast image understanding.

Usage:
    from gemini_client import GeminiClient

    client = GeminiClient()

    # Analyze an image
    description = await client.analyze_image("/path/to/image.jpg")

    # Analyze with custom prompt
    result = await client.analyze_image(
        "/path/to/screenshot.png",
        prompt="Extract all text visible in this screenshot"
    )

    # Analyze a document/form
    fields = await client.analyze_document("/path/to/form.pdf")
"""

import os
import base64
import logging
import mimetypes
from typing import Optional, Dict, Any, List, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Client for Google Gemini API with focus on vision capabilities.

    Supports:
    - Image analysis (photos, screenshots, diagrams)
    - Document understanding (forms, PDFs converted to images)
    - Text extraction from images
    - Multi-modal prompts (text + image)
    """

    DEFAULT_MODEL = "gemini-2.0-flash"
    SUPPORTED_MIME_TYPES = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.heic': 'image/heic',
        '.heif': 'image/heif',
    }

    def __init__(
        self,
        api_key: str = None,
        model: str = None
    ):
        """
        Initialize Gemini client.

        Args:
            api_key: Google API key. If not provided, reads from GOOGLE_API_KEY env var
            model: Model to use. Defaults to gemini-2.0-flash
        """
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        self.model_name = model or self.DEFAULT_MODEL
        self._client = None

    def _get_client(self):
        """Lazy-load the Gemini client."""
        if self._client is None:
            try:
                import google.generativeai as genai

                if not self.api_key:
                    raise ValueError(
                        "Gemini API key not configured. "
                        "Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable."
                    )

                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(self.model_name)
                logger.info(f"Gemini client initialized with model: {self.model_name}")

            except ImportError:
                raise ImportError(
                    "google-generativeai package not installed. "
                    "Run: pip install google-generativeai"
                )

        return self._client

    def is_available(self) -> bool:
        """Check if Gemini client is configured and available."""
        try:
            _ = self._get_client()
            return True
        except Exception as e:
            logger.debug(f"Gemini not available: {e}")
            return False

    async def analyze_image(
        self,
        image_path: str,
        prompt: str = None,
        extract_text: bool = False
    ) -> str:
        """
        Analyze an image using Gemini vision.

        Args:
            image_path: Path to image file
            prompt: Custom prompt for analysis. If not provided, uses default.
            extract_text: If True, focuses on text extraction

        Returns:
            Analysis result as string
        """
        client = self._get_client()

        # Validate file exists
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Get MIME type
        suffix = path.suffix.lower()
        mime_type = self.SUPPORTED_MIME_TYPES.get(suffix)
        if not mime_type:
            # Try to guess
            mime_type, _ = mimetypes.guess_type(str(path))
            if not mime_type or not mime_type.startswith('image/'):
                raise ValueError(f"Unsupported image format: {suffix}")

        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = f.read()

        # Prepare image part
        import google.generativeai as genai
        image_part = {
            "mime_type": mime_type,
            "data": image_data
        }

        # Prepare prompt
        if prompt:
            full_prompt = prompt
        elif extract_text:
            full_prompt = (
                "Extract all visible text from this image. "
                "Preserve the structure and formatting as much as possible. "
                "If it's a form, identify field labels and their values."
            )
        else:
            full_prompt = (
                "Describe this image in detail. "
                "If it's a document or form, extract the key information. "
                "If it's a screenshot, describe what you see including any text. "
                "If it's a diagram, explain what it represents."
            )

        # Generate response
        try:
            response = client.generate_content([full_prompt, image_part])
            return response.text
        except Exception as e:
            logger.error(f"Gemini image analysis failed: {e}")
            raise

    async def analyze_screenshot(self, image_path: str) -> str:
        """
        Specialized analysis for screenshots.

        Extracts UI elements, text, and describes what's shown.

        Args:
            image_path: Path to screenshot file

        Returns:
            Screenshot analysis
        """
        return await self.analyze_image(
            image_path,
            prompt=(
                "This is a screenshot. Please:\n"
                "1. Describe what application or website is shown\n"
                "2. Extract all visible text\n"
                "3. Identify any important UI elements (buttons, forms, menus)\n"
                "4. Note any error messages or notifications\n"
                "5. Summarize the main purpose/content of this screen"
            )
        )

    async def analyze_document(
        self,
        image_path: str,
        document_type: str = None
    ) -> Dict[str, Any]:
        """
        Analyze a document image (form, invoice, etc.).

        Args:
            image_path: Path to document image
            document_type: Optional hint about document type (form, invoice, contract, etc.)

        Returns:
            Dict with extracted fields and summary
        """
        type_hint = f"This appears to be a {document_type}. " if document_type else ""

        prompt = (
            f"{type_hint}Please analyze this document:\n"
            "1. Identify the type of document\n"
            "2. Extract all key fields and their values\n"
            "3. Note any important dates, amounts, or names\n"
            "4. Identify any signatures or stamps\n"
            "5. Provide a brief summary\n\n"
            "Format your response as:\n"
            "DOCUMENT TYPE: [type]\n"
            "KEY FIELDS:\n- [field]: [value]\n"
            "SUMMARY: [brief summary]"
        )

        result = await self.analyze_image(image_path, prompt)

        # Parse the structured response
        parsed = {
            'raw_response': result,
            'document_type': None,
            'fields': {},
            'summary': None
        }

        try:
            lines = result.split('\n')
            current_section = None

            for line in lines:
                line = line.strip()
                if line.startswith('DOCUMENT TYPE:'):
                    parsed['document_type'] = line.replace('DOCUMENT TYPE:', '').strip()
                elif line.startswith('KEY FIELDS:'):
                    current_section = 'fields'
                elif line.startswith('SUMMARY:'):
                    parsed['summary'] = line.replace('SUMMARY:', '').strip()
                    current_section = 'summary'
                elif current_section == 'fields' and line.startswith('-'):
                    # Parse field: value
                    if ':' in line:
                        key, value = line[1:].split(':', 1)
                        parsed['fields'][key.strip()] = value.strip()
                elif current_section == 'summary' and line:
                    parsed['summary'] = (parsed['summary'] or '') + ' ' + line

        except Exception as e:
            logger.warning(f"Could not parse structured response: {e}")

        return parsed

    async def extract_text(self, image_path: str) -> str:
        """
        Extract text from an image (OCR-like functionality).

        Args:
            image_path: Path to image file

        Returns:
            Extracted text
        """
        return await self.analyze_image(image_path, extract_text=True)

    async def compare_images(
        self,
        image_path_1: str,
        image_path_2: str,
        comparison_type: str = "general"
    ) -> str:
        """
        Compare two images and describe differences.

        Args:
            image_path_1: Path to first image
            image_path_2: Path to second image
            comparison_type: Type of comparison (general, ui_changes, document_diff)

        Returns:
            Comparison analysis
        """
        client = self._get_client()
        import google.generativeai as genai

        # Read both images
        images = []
        for path in [image_path_1, image_path_2]:
            p = Path(path)
            suffix = p.suffix.lower()
            mime_type = self.SUPPORTED_MIME_TYPES.get(suffix, 'image/jpeg')

            with open(path, 'rb') as f:
                images.append({
                    "mime_type": mime_type,
                    "data": f.read()
                })

        prompts = {
            "general": "Compare these two images and describe the key differences.",
            "ui_changes": "Compare these two UI screenshots. What elements have changed?",
            "document_diff": "Compare these two document images. What content has changed?"
        }

        prompt = prompts.get(comparison_type, prompts["general"])

        response = client.generate_content([prompt, images[0], images[1]])
        return response.text

    async def describe_for_email(self, image_path: str) -> str:
        """
        Generate a description suitable for including in an email.

        Args:
            image_path: Path to image

        Returns:
            Email-friendly description
        """
        return await self.analyze_image(
            image_path,
            prompt=(
                "Describe this image in 2-3 sentences that could be used in a "
                "professional email. Be concise but capture the key information. "
                "If it's a chart or data, mention the key numbers. "
                "If it's a screenshot, note what's being shown."
            )
        )


# ==================
# CONVENIENCE FUNCTIONS
# ==================

async def analyze_image(image_path: str, prompt: str = None) -> str:
    """
    Convenience function to analyze an image.

    Args:
        image_path: Path to image file
        prompt: Optional custom prompt

    Returns:
        Analysis result
    """
    client = GeminiClient()
    return await client.analyze_image(image_path, prompt)


async def extract_text_from_image(image_path: str) -> str:
    """
    Convenience function to extract text from an image.

    Args:
        image_path: Path to image file

    Returns:
        Extracted text
    """
    client = GeminiClient()
    return await client.extract_text(image_path)


# ==================
# TESTING
# ==================

if __name__ == "__main__":
    import asyncio

    async def test():
        client = GeminiClient()

        if not client.is_available():
            print("Gemini not available. Set GOOGLE_API_KEY environment variable.")
            return

        print("Gemini client is available!")
        print(f"Model: {client.model_name}")

        # Test with a sample image if provided
        import sys
        if len(sys.argv) > 1:
            image_path = sys.argv[1]
            print(f"\nAnalyzing: {image_path}")
            result = await client.analyze_image(image_path)
            print(f"\nResult:\n{result}")

    asyncio.run(test())
