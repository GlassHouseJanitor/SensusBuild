import os
import sys
import re
import glob
import logging
import traceback
import shutil
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
from flask_bootstrap import Bootstrap5
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create the Flask app
app = Flask(__name__)
bootstrap = Bootstrap5(app)

# Configuration
app.config['SECRET_KEY'] = os.urandom(24)
BASE_DIR = os.environ.get('EB_SCRIPT_DIR', os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join('/tmp', 'uploads')  # Use /tmp which is always writable
TEMP_FOLDER = os.path.join('/tmp', 'uploads', 'temp_input')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['TEMP_FOLDER'] = TEMP_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'csv'}
app.config['MAX_FILES'] = 30
app.config['PROCESSOR_SCRIPT'] = os.path.join(BASE_DIR, 'nextus_census_processor.py')

# Ensure upload directories exist with proper permissions
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
try:
    os.chmod(UPLOAD_FOLDER, 0o755)  # rwxr-xr-x
    logger.info(f"Set permissions on {UPLOAD_FOLDER}")
except Exception as e:
    logger.warning(f"Could not set permissions on {UPLOAD_FOLDER}: {str(e)}")

os.makedirs(TEMP_FOLDER, exist_ok=True)
try:
    os.chmod(TEMP_FOLDER, 0o755)  # rwxr-xr-x
    logger.info(f"Set permissions on {TEMP_FOLDER}")
except Exception as e:
    logger.warning(f"Could not set permissions on {TEMP_FOLDER}: {str(e)}")

# Context processor to make year available to all templates
@app.context_processor
def inject_year():
    return {'year': datetime.now().year}

def allowed_file(filename):
    """Check if the file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def process_with_nextus_script(filepaths):
    """
    Process multiple CSV files using the nextus_census_processor module
    Returns the path to the generated Excel report
    """
    temp_input_dir = app.config['TEMP_FOLDER']
    try:
        # Create temporary input directory for the files
        os.makedirs(temp_input_dir, exist_ok=True)
        logger.info(f"Created temp directory: {temp_input_dir}")
        
        # Copy all files to temp input directory
        for filepath in filepaths:
            if os.path.exists(filepath):  # Only copy if the file exists
                filename = os.path.basename(filepath)
                temp_filepath = os.path.join(temp_input_dir, filename)
                shutil.copy2(filepath, temp_filepath)  # Use copy2 instead of rename
                logger.info(f"Copied {filepath} to {temp_filepath}")
        
        # Get current month and year from the first file
        first_file = os.path.basename(filepaths[0])
        logger.info(f"Extracting date from filename: {first_file}")
        date_match = re.search(r'(\d{4})[-_]?(\d{2})[-_]?\d{2}', first_file)
        if not date_match:
            raise Exception(f"Could not extract date from filename: {first_file}")
        
        year = int(date_match.group(1))
        month = int(date_match.group(2))
        logger.info(f"Extracted date: year={year}, month={month}")
        
        # Import the nextus processor module
        import importlib.util
        logger.info(f"Importing processor script from {app.config['PROCESSOR_SCRIPT']}")
        spec = importlib.util.spec_from_file_location("nextus_processor", app.config['PROCESSOR_SCRIPT'])
        processor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(processor)
        
        # Process the files using the nextus processor
        logger.info(f"Processing files with processor, input_folder={temp_input_dir}")
        output_path = processor.process_census_files(
            input_folder=temp_input_dir,
            output_folder=app.config['UPLOAD_FOLDER'],
            month=month,
            year=year
        )
        
        # Clean up temporary input directory
        logger.info(f"Cleaning up temp directory: {temp_input_dir}")
        shutil.rmtree(temp_input_dir, ignore_errors=True)
        
        # Return the output path if available
        return output_path
        
    except Exception as e:
        # Clean up temporary directory in case of error
        error_traceback = traceback.format_exc()
        logger.error(f"Error in process_with_nextus_script: {str(e)}\n{error_traceback}")
        try:
            if os.path.exists(temp_input_dir):
                shutil.rmtree(temp_input_dir, ignore_errors=True)
        except:
            pass
        raise Exception(f"Error processing files: {str(e)}")

def process_csv_files(filepaths):
    """Wrapper function to process CSV files and return the output path"""
    try:
        # Process all files with the nextus script
        output_path = process_with_nextus_script(filepaths)
        return output_path
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Error in process_csv_files: {str(e)}\n{error_traceback}")
        raise Exception(f"Error processing files: {str(e)}")

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    """Main page for file upload"""
    if request.method == 'POST':
        # Check if files were uploaded
        if 'files[]' not in request.files:
            flash('No files selected', 'danger')
            return redirect(request.url)
        
        files = request.files.getlist('files[]')
        
        # If no files selected
        if not files or files[0].filename == '':
            flash('No files selected', 'danger')
            return redirect(request.url)
        
        # Check number of files
        if len(files) > app.config['MAX_FILES']:
            flash(f'Too many files. Maximum allowed is {app.config["MAX_FILES"]}', 'danger')
            return redirect(request.url)
        
        filepaths = []  # Define filepaths here so it's available in the except block
        try:
            # Process each file
            for file in files:
                if file and allowed_file(file.filename):
                    try:
                        filename = secure_filename(file.filename)
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        logger.info(f"Saving uploaded file: {filename} to {filepath}")
                        file.save(filepath)
                        logger.info(f"Successfully saved file: {filename}")
                        filepaths.append(filepath)
                    except Exception as e:
                        logger.error(f"Error saving file {file.filename}: {str(e)}")
                        flash(f'Error saving file {file.filename}: {str(e)}', 'danger')
                        # Clean up any files already saved
                        for fp in filepaths:
                            try:
                                if os.path.exists(fp):
                                    os.remove(fp)
                            except Exception as cleanup_err:
                                logger.error(f"Error cleaning up file {fp}: {str(cleanup_err)}")
                        return redirect(request.url)
                else:
                    # Clean up any files already saved
                    for fp in filepaths:
                        try:
                            if os.path.exists(fp):
                                os.remove(fp)
                        except Exception as cleanup_err:
                            logger.error(f"Error cleaning up file {fp}: {str(cleanup_err)}")
                    flash('One or more files have invalid type. Please upload only CSV files.', 'danger')
                    return redirect(request.url)
            
            # Process the files using the nextus processor
            logger.info(f"Starting CSV file processing for {len(filepaths)} files")
            output_path = process_csv_files(filepaths)
            
            # Clean up the original files
            for filepath in filepaths:
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        logger.info(f"Removed original file: {filepath}")
                except Exception as e:
                    logger.warning(f"Could not remove file {filepath}: {str(e)}")
            
            # Redirect to the reports page instead of back to upload
            flash('Files processed successfully. You can now download the generated report.', 'success')
            return redirect(url_for('list_reports'))
        
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(f"Error processing files: {str(e)}\n{error_traceback}")
            
            # Clean up any files in case of error
            for filepath in filepaths:
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception as cleanup_err:
                    logger.error(f"Error cleaning up file {filepath}: {str(cleanup_err)}")
            
            flash(f'Error processing files: {str(e)}', 'danger')
            return redirect(request.url)
    
    return render_template('upload.html')

@app.route('/reports')
def list_reports():
    """Display a list of generated reports available for download"""
    reports_dir = app.config['UPLOAD_FOLDER']
    excel_files = glob.glob(os.path.join(reports_dir, "Census_*.xlsx"))
    
    # Get relative paths and creation times
    reports = []
    for file_path in excel_files:
        filename = os.path.basename(file_path)
        try:
            creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
        except:
            creation_time = datetime.now()  # Default if can't get creation time
            
        reports.append({
            'filename': filename,
            'created': creation_time,
            'path': filename
        })
    
    # Sort by creation time (newest first)
    reports = sorted(reports, key=lambda x: x['created'], reverse=True)
    
    return render_template('reports.html', reports=reports)

@app.route('/download/<filename>')
def download_report(filename):
    """Endpoint to download a specific report file"""
    # Secure the filename to prevent directory traversal attacks
    filename = secure_filename(filename)
    
    # Ensure the file exists and has an xlsx extension
    if not filename.endswith('.xlsx'):
        flash('Invalid file type requested', 'danger')
        return redirect(url_for('list_reports'))
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        flash('File not found', 'danger')
        return redirect(url_for('list_reports'))
    
    logger.info(f"Sending file for download: {file_path}")
    
    # Send the file for download
    return send_file(file_path, as_attachment=True)

@app.route('/check_permissions')
def check_permissions():
    """Diagnostic endpoint to check directory permissions"""
    upload_dir = app.config['UPLOAD_FOLDER']
    results = {
        'upload_directory': upload_dir,
        'exists': os.path.exists(upload_dir),
        'is_writable': os.access(upload_dir, os.W_OK) if os.path.exists(upload_dir) else False,
        'stat_info': str(os.stat(upload_dir)) if os.path.exists(upload_dir) else 'N/A',
        'current_user': os.getenv('USER', 'unknown'),
        'generated_files': []
    }
    
    # Check for existing reports
    if os.path.exists(upload_dir):
        excel_files = glob.glob(os.path.join(upload_dir, "*.xlsx"))
        for file_path in excel_files:
            results['generated_files'].append({
                'name': os.path.basename(file_path),
                'size': os.path.getsize(file_path),
                'created': datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
            })
    
    return render_template('check_permissions.html', results=results)

@app.errorhandler(413)
def too_large(e):
    """Handle file size exceeding the maximum limit"""
    flash('One or more files are too large. Maximum size per file is 16MB.', 'danger')
    return redirect(url_for('upload_file'))

if __name__ == '__main__':
    # Verify the nextus processor script exists
    if not Path(app.config['PROCESSOR_SCRIPT']).is_file():
        logger.error(f"Error: Could not find {app.config['PROCESSOR_SCRIPT']}. Please ensure it's in the same directory as app.py")
        sys.exit(1)
    
    # Use port 5001 instead of 5000 to avoid conflict with AirPlay
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)