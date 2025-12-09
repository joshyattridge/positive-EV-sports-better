"""
Unit tests for Action Logger module
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.automation.action_logger import ActionLogger


@pytest.fixture
def temp_log_file():
    """Create a temporary log file for testing"""
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
    temp_path = temp_file.name
    temp_file.close()
    
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def action_logger(temp_log_file):
    """Create an ActionLogger instance with temporary file"""
    return ActionLogger(log_path=temp_log_file)


class TestActionLoggerInitialization:
    """Test ActionLogger initialization"""
    
    def test_initialization_creates_empty_dict(self, temp_log_file):
        """Test initialization with new file"""
        logger = ActionLogger(log_path=temp_log_file)
        assert logger.action_logs == {}
        assert logger.current_website is None
        assert logger.current_run_timestamp is None
    
    def test_initialization_loads_existing_logs(self, temp_log_file):
        """Test initialization loads existing logs"""
        # Create a log file with existing data
        existing_data = {
            "www.example.com": {
                "20240101_120000": [
                    {"tool": "browser_navigate", "args": {"url": "https://example.com"}}
                ]
            }
        }
        
        with open(temp_log_file, 'w') as f:
            json.dump(existing_data, f)
        
        logger = ActionLogger(log_path=temp_log_file)
        assert "www.example.com" in logger.action_logs
    
    def test_load_sensitive_values(self, action_logger):
        """Test that sensitive values are loaded from environment"""
        with patch.dict('os.environ', {
            'TEST_USERNAME': 'testuser',
            'TEST_PASSWORD': 'secret123',
            'API_KEY': 'key123'
        }):
            logger = ActionLogger()
            assert 'testuser' in logger.sensitive_values
            assert 'secret123' in logger.sensitive_values
            assert 'key123' in logger.sensitive_values


class TestExtractDomain:
    """Test domain extraction"""
    
    def test_extract_domain_full_url(self, action_logger):
        """Test extracting domain from full URL"""
        domain = action_logger._extract_domain('https://www.example.com/path')
        assert domain in ['www.example.com', 'example.com']
    
    def test_extract_domain_without_protocol(self, action_logger):
        """Test extracting domain without protocol"""
        domain = action_logger._extract_domain('www.example.com')
        assert 'example.com' in domain
    
    def test_extract_domain_with_port(self, action_logger):
        """Test extracting domain with port"""
        domain = action_logger._extract_domain('https://www.example.com:8080/path')
        assert 'example.com' in domain
    
    def test_extract_domain_subdomain(self, action_logger):
        """Test extracting domain with subdomain"""
        domain = action_logger._extract_domain('https://sports.example.com')
        assert 'example.com' in domain


class TestStartNewRun:
    """Test starting new automation runs"""
    
    def test_start_new_run_generates_timestamp(self, action_logger):
        """Test that starting a new run generates a timestamp"""
        timestamp = action_logger.start_new_run()
        
        assert action_logger.current_run_timestamp is not None
        assert len(timestamp) > 0
        assert '_' in timestamp
    
    def test_start_new_run_with_url(self, action_logger):
        """Test starting a new run with URL sets website"""
        timestamp = action_logger.start_new_run('https://www.example.com')
        
        assert action_logger.current_website is not None
        assert 'example.com' in action_logger.current_website
    
    def test_start_new_run_timestamp_format(self, action_logger):
        """Test timestamp has correct format"""
        timestamp = action_logger.start_new_run()
        
        # Should be in format YYYYMMDD_HHMMSS
        parts = timestamp.split('_')
        assert len(parts) == 2
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS


class TestUpdateCurrentWebsite:
    """Test updating current website"""
    
    def test_update_current_website(self, action_logger):
        """Test updating current website from URL"""
        action_logger.update_current_website('https://www.example.com/path')
        
        assert action_logger.current_website is not None
        assert 'example.com' in action_logger.current_website
    
    def test_update_current_website_different_urls(self, action_logger):
        """Test updating website with different URLs"""
        action_logger.update_current_website('https://www.example.com')
        first_website = action_logger.current_website
        
        action_logger.update_current_website('https://www.another.com')
        second_website = action_logger.current_website
        
        assert first_website != second_website


class TestSanitizeSensitiveData:
    """Test sensitive data sanitization"""
    
    def test_sanitize_password_field(self, action_logger):
        """Test password field is redacted"""
        args = {
            'element': 'password',
            'text': 'secret123'
        }
        
        sanitized = action_logger._sanitize_sensitive_data(args)
        assert sanitized['text'] == '[REDACTED]'
    
    def test_sanitize_username_field(self, action_logger):
        """Test username field is redacted"""
        args = {
            'element': 'username input',
            'text': 'myusername'
        }
        
        sanitized = action_logger._sanitize_sensitive_data(args)
        assert sanitized['text'] == '[REDACTED]'
    
    def test_sanitize_email_field(self, action_logger):
        """Test email field is redacted"""
        args = {
            'element': 'email address',
            'text': 'user@example.com'
        }
        
        sanitized = action_logger._sanitize_sensitive_data(args)
        assert sanitized['text'] == '[REDACTED]'
    
    def test_sanitize_known_credentials(self, action_logger):
        """Test known credentials from env are redacted"""
        with patch.object(action_logger, 'sensitive_values', {'secret_password', 'my_username'}):
            args = {
                'element': 'input field',
                'text': 'secret_password'
            }
            
            sanitized = action_logger._sanitize_sensitive_data(args)
            assert sanitized['text'] == '[REDACTED]'
    
    def test_sanitize_preserves_normal_data(self, action_logger):
        """Test normal data is not redacted"""
        args = {
            'element': 'search box',
            'text': 'Arsenal vs Chelsea'
        }
        
        sanitized = action_logger._sanitize_sensitive_data(args)
        assert sanitized['text'] == 'Arsenal vs Chelsea'
    
    def test_sanitize_preserves_non_sensitive_keys(self, action_logger):
        """Test non-sensitive keys are preserved"""
        args = {
            'url': 'https://example.com',
            'timeout': 5000
        }
        
        sanitized = action_logger._sanitize_sensitive_data(args)
        assert sanitized['url'] == 'https://example.com'
        assert sanitized['timeout'] == 5000


class TestRecordToolCall:
    """Test tool call recording"""
    
    def test_record_tool_call_basic(self, action_logger):
        """Test basic tool call recording"""
        action_logger.start_new_run('https://www.example.com')
        
        action_logger.record_tool_call(
            'browser_navigate',
            {'url': 'https://www.example.com'}
        )
        
        website = action_logger.current_website
        timestamp = action_logger.current_run_timestamp
        
        assert website in action_logger.action_logs
        assert timestamp in action_logger.action_logs[website]
        assert len(action_logger.action_logs[website][timestamp]) == 1
    
    def test_record_multiple_tool_calls(self, action_logger):
        """Test recording multiple tool calls"""
        action_logger.start_new_run('https://www.example.com')
        
        action_logger.record_tool_call('browser_navigate', {'url': 'https://www.example.com'})
        action_logger.record_tool_call('browser_click', {'element': 'button'})
        action_logger.record_tool_call('browser_type', {'element': 'input', 'text': 'test'})
        
        website = action_logger.current_website
        timestamp = action_logger.current_run_timestamp
        
        assert len(action_logger.action_logs[website][timestamp]) == 3
    
    def test_record_tool_call_sanitizes_sensitive_data(self, action_logger):
        """Test that tool calls are sanitized before recording"""
        action_logger.start_new_run('https://www.example.com')
        
        action_logger.record_tool_call(
            'browser_type',
            {'element': 'password', 'text': 'secret123'}
        )
        
        website = action_logger.current_website
        timestamp = action_logger.current_run_timestamp
        recorded = action_logger.action_logs[website][timestamp][0]
        
        assert recorded['args']['text'] == '[REDACTED]'
    
    def test_record_tool_call_saves_to_file(self, action_logger, temp_log_file):
        """Test that tool calls are saved to file"""
        action_logger.start_new_run('https://www.example.com')
        action_logger.record_tool_call('browser_navigate', {'url': 'https://www.example.com'})
        
        # Verify file was written
        with open(temp_log_file, 'r') as f:
            saved_data = json.load(f)
        
        assert len(saved_data) > 0


class TestGetAllToolCalls:
    """Test retrieving tool calls"""
    
    def test_get_all_tool_calls_empty(self, action_logger):
        """Test getting tool calls from empty log"""
        calls = action_logger.get_all_tool_calls()
        assert calls == []
    
    def test_get_all_tool_calls_with_data(self, action_logger):
        """Test getting all tool calls"""
        action_logger.start_new_run('https://www.example.com')
        action_logger.record_tool_call('browser_navigate', {'url': 'https://www.example.com'})
        action_logger.record_tool_call('browser_click', {'element': 'button'})
        
        calls = action_logger.get_all_tool_calls()
        assert len(calls) == 2
    
    def test_get_tool_calls_filtered_by_website(self, action_logger):
        """Test getting tool calls filtered by website"""
        action_logger.start_new_run('https://www.example.com')
        action_logger.record_tool_call('browser_navigate', {'url': 'https://www.example.com'})
        
        action_logger.start_new_run('https://www.another.com')
        action_logger.record_tool_call('browser_navigate', {'url': 'https://www.another.com'})
        
        # Get calls for specific website
        example_calls = action_logger.get_all_tool_calls(website=action_logger.current_website)
        
        # Should have at least one call
        assert len(example_calls) >= 1


class TestGetRunSummary:
    """Test run summary"""
    
    def test_get_run_summary_no_active_run(self, action_logger):
        """Test summary with no active run"""
        summary = action_logger.get_run_summary()
        assert 'error' in summary
    
    def test_get_run_summary_with_data(self, action_logger):
        """Test summary with recorded tool calls"""
        action_logger.start_new_run('https://www.example.com')
        action_logger.record_tool_call('browser_navigate', {'url': 'https://www.example.com'})
        action_logger.record_tool_call('browser_click', {'element': 'button'})
        
        summary = action_logger.get_run_summary()
        
        assert summary['total_tool_calls'] == 2
        assert 'website' in summary
        assert 'timestamp' in summary
    
    def test_get_run_summary_empty_run(self, action_logger):
        """Test summary with no tool calls"""
        action_logger.start_new_run('https://www.example.com')
        
        summary = action_logger.get_run_summary()
        
        assert summary['total_tool_calls'] == 0


class TestPrintRunSummary:
    """Test printing run summary"""
    
    def test_print_run_summary_no_error(self, action_logger, capsys):
        """Test that print doesn't raise errors"""
        action_logger.start_new_run('https://www.example.com')
        action_logger.record_tool_call('browser_navigate', {'url': 'https://www.example.com'})
        
        action_logger.print_run_summary()
        
        captured = capsys.readouterr()
        assert 'tool call' in captured.out.lower()


class TestSaveAndLoad:
    """Test saving and loading functionality"""
    
    def test_save_action_logs(self, action_logger, temp_log_file):
        """Test that action logs are saved properly"""
        action_logger.start_new_run('https://www.example.com')
        action_logger.record_tool_call('browser_navigate', {'url': 'https://www.example.com'})
        
        # Force save
        action_logger._save_action_logs()
        
        # Verify file exists and contains data
        assert Path(temp_log_file).exists()
        
        with open(temp_log_file, 'r') as f:
            data = json.load(f)
        
        assert len(data) > 0
    
    def test_load_action_logs(self, temp_log_file):
        """Test loading existing action logs"""
        # Create a log file with data
        test_data = {
            "www.example.com": {
                "20240101_120000": [
                    {"tool": "browser_navigate", "args": {"url": "https://example.com"}}
                ]
            }
        }
        
        with open(temp_log_file, 'w') as f:
            json.dump(test_data, f)
        
        logger = ActionLogger(log_path=temp_log_file)
        
        assert "www.example.com" in logger.action_logs
        assert "20240101_120000" in logger.action_logs["www.example.com"]
