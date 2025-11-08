# What's New - Edit Guide

## Overview
The "What's New" announcements are stored in `whats_new.json` and can be edited without changing any code.

## File Location
```
backend/app/api/v1/whats_new.json
```

## How to Edit

Simply edit the `whats_new.json` file with your text editor. The changes will be live immediately (no restart needed for most changes).

### JSON Structure

```json
[
  {
    "version": "0.2.0",
    "date": "2025-01-17",
    "title": "Your Update Title",
    "description": "Brief description of the update",
    "highlights": [
      "First highlight or feature",
      "Second highlight or feature",
      "Third highlight or feature"
    ]
  }
]
```

### Fields Explanation

- **version** (required): Version number (e.g., "1.0.0", "2.1.3")
- **date** (required): Release date in YYYY-MM-DD format
- **title** (required): Short, catchy title for the update
- **description** (required): One-sentence description
- **highlights** (optional): Array of bullet points highlighting key features

### Tips

1. **Order Matters**: The first item in the array is shown as the "latest" update
2. **Keep It Short**: Users only see the first/latest announcement in detail
3. **Dates**: Use YYYY-MM-DD format (e.g., "2025-01-17")
4. **Highlights**: 3-5 bullet points work best
5. **Validation**: The file must be valid JSON (use a JSON validator if unsure)

### Example - Adding a New Update

```json
[
  {
    "version": "0.3.0",
    "date": "2025-02-01",
    "title": "New Profile Scraping Features",
    "description": "Enhanced profile scraping with company information and skills extraction",
    "highlights": [
      "Extract company details from profiles",
      "Skills and endorsements scraping",
      "Improved error handling for private profiles",
      "Batch processing for multiple profiles"
    ]
  },
  {
    "version": "0.2.0",
    "date": "2025-01-17",
    "title": "Enhanced Server Configuration",
    "description": "New server information endpoint and improved error handling",
    "highlights": [
      "Dynamic server restrictions display",
      "Secure server-call validation via self-check",
      "What's new announcements",
      "Better error messages for restricted features"
    ]
  }
]
```

### Common Mistakes to Avoid

❌ **Don't forget commas** between items:
```json
[
  { ... }  // Missing comma here!
  { ... }
]
```

✅ **Do add commas**:
```json
[
  { ... },  // Comma here
  { ... }
]
```

❌ **Don't use trailing commas**:
```json
[
  { ... },
  { ... },  // Remove this trailing comma
]
```

✅ **No comma on last item**:
```json
[
  { ... },
  { ... }  // No comma on last item
]
```

### Validation

Before committing changes, you can validate your JSON:
- Online: https://jsonlint.com/
- Command line: `python -m json.tool whats_new.json`
- Most code editors highlight JSON syntax errors

### Testing

After editing:
1. Save the file
2. The backend will automatically load it on next request
3. Check the dashboard to see your changes

### Need Help?

If you see errors in the logs like:
```
Error loading What's New from JSON: ...
```

It means there's a syntax error in your JSON. Use a validator to find and fix it.


