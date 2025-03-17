# Census Report Generator

A Flask web application that processes attendance report CSV files and generates formatted census reports using the Nextus Census Processor.

## Features

- Upload multiple CSV attendance report files (up to 30 files)
- Process files using the Nextus Census Processor
- Generate formatted Excel reports with census data
- Clean interface for file upload and processing
- Automatic file cleanup and error handling

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

## Installation

1. Clone the repository:
```bash
git clone [your-repository-url]
cd [repository-name]
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
- On Windows:
```bash
venv\Scripts\activate
```
- On macOS/Linux:
```bash
source venv/bin/activate
```

4. Install required packages:
```bash
pip install -r requirements.txt
```

## Configuration

1. Ensure the `uploads` directory exists:
```bash
mkdir uploads
```

2. Configure the output directory in `nextus_census_processor.py` if needed.

## Usage

1. Start the Flask application:
```bash
python app.py
```

2. Open a web browser and navigate to `http://localhost:5000`

3. Upload CSV attendance report files (up to 30 files)

4. The application will process the files and generate a formatted census report in the configured output directory

## Project Structure

```
.
├── app.py                      # Main Flask application
├── nextus_census_processor.py  # Census processing script
├── requirements.txt            # Python dependencies
├── templates/                  # HTML templates
│   ├── base.html
│   └── upload.html
└── uploads/                    # Temporary file storage
```

## Error Handling

- The application validates file types and counts
- Provides clear error messages for invalid files or processing issues
- Automatically cleans up temporary files
- Handles processing errors gracefully

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Your chosen license]

## Support

[Your contact information or support instructions] 