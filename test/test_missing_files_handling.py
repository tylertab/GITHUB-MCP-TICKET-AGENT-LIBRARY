import pytest
from unittest.mock import patch, MagicMock
import sys
import pathlib

# Add src to path for imports
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ticketwatcher.handlers import (
    _paths_from_issue_text,
    _fetch_slice,
    _fetch_symbol_slice,
    handle_issue_event
)


class TestMissingFilesHandling:
    """Test cases for when users don't provide file information or files don't exist."""
    
    def test_no_file_paths_in_issue_text(self):
        """Test when issue has no file references."""
        issue_text = "Something is broken but no file paths mentioned"
        paths = _paths_from_issue_text(issue_text)
        assert paths == []
    
    def test_empty_issue_text(self):
        """Test when issue text is empty or None."""
        assert _paths_from_issue_text("") == []
        assert _paths_from_issue_text(None) == []
        assert _paths_from_issue_text("   ") == []
    
    def test_invalid_file_paths_only(self):
        """Test when issue mentions files that don't exist."""
        issue_text = 'File "nonexistent/file.py", line 10'
        paths = _paths_from_issue_text(issue_text)
        assert paths == [("nonexistent/file.py", 10)]
        # The parsing works, but file fetching should handle non-existence
    
    @patch('ticketwatcher.handlers.file_exists')
    @patch('ticketwatcher.handlers.get_file_text')
    def test_fetch_slice_file_not_exists(self, mock_get_file, mock_file_exists):
        """Test _fetch_slice when file doesn't exist."""
        mock_file_exists.return_value = False
        
        result = _fetch_slice("nonexistent.py", "main", 10, 60)
        assert result is None
        mock_get_file.assert_not_called()
    
    @patch('ticketwatcher.handlers.file_exists')
    @patch('ticketwatcher.handlers.get_file_text')
    def test_fetch_slice_api_error(self, mock_get_file, mock_file_exists):
        """Test _fetch_slice when GitHub API fails."""
        mock_file_exists.return_value = True
        mock_get_file.side_effect = Exception("API Error")
        
        result = _fetch_slice("src/app/auth.py", "main", 10, 60)
        assert result is None
    
    @patch('ticketwatcher.handlers.file_exists')
    @patch('ticketwatcher.handlers.get_file_text')
    def test_fetch_symbol_slice_file_not_exists(self, mock_get_file, mock_file_exists):
        """Test _fetch_symbol_slice when file doesn't exist."""
        mock_file_exists.return_value = False
        
        result = _fetch_symbol_slice("nonexistent.py", "main", "some_function", 60)
        assert result is None
        mock_get_file.assert_not_called()
    
    @patch('ticketwatcher.handlers.file_exists')
    @patch('ticketwatcher.handlers.get_file_text')
    def test_fetch_symbol_slice_api_error(self, mock_get_file, mock_file_exists):
        """Test _fetch_symbol_slice when GitHub API fails."""
        mock_file_exists.return_value = True
        mock_get_file.side_effect = Exception("Network timeout")
        
        result = _fetch_symbol_slice("src/app/auth.py", "main", "get_user_profile", 60)
        assert result is None
    
    @patch('ticketwatcher.handlers.get_default_branch')
    @patch('ticketwatcher.handlers.add_issue_comment')
    @patch('ticketwatcher.handlers._fetch_slice')
    def test_handle_issue_no_files_found(self, mock_fetch, mock_comment, mock_branch):
        """Test handle_issue_event when no files can be parsed from issue."""
        mock_branch.return_value = "main"
        mock_fetch.return_value = None  # No files found
        
        event = {
            "action": "opened",
            "issue": {
                "number": 123,
                "title": "Something broken",
                "body": "No file paths here",
                "labels": [{"name": "agent-fix"}]
            }
        }
        
        result = handle_issue_event(event)
        assert result is None  # Should not create PR
        # Should comment asking for more info (this depends on your agent's response)
    
    @patch('ticketwatcher.handlers.get_default_branch')
    @patch('ticketwatcher.handlers.add_issue_comment')
    @patch('ticketwatcher.handlers.TicketWatcherAgent')
    def test_handle_issue_agent_requests_context(self, mock_agent_class, mock_comment, mock_branch):
        """Test when agent requests more context due to insufficient info."""
        mock_branch.return_value = "main"
        
        # Mock agent to return request_context
        mock_agent = MagicMock()
        mock_agent.run_two_rounds.return_value = {
            "action": "request_context",
            "needs": [],
            "reason": "Need more file information"
        }
        mock_agent_class.return_value = mock_agent
        
        event = {
            "action": "opened",
            "issue": {
                "number": 123,
                "title": "Bug report",
                "body": "Something is wrong",
                "labels": [{"name": "agent-fix"}]
            }
        }
        
        result = handle_issue_event(event)
        assert result is None
        
        # Should add helpful comment
        mock_comment.assert_called_once()
        call_args = mock_comment.call_args[0]
        assert call_args[0] == 123  # issue number
        assert "more context" in call_args[1].lower()
    
    def test_paths_parsing_with_mixed_valid_invalid(self):
        """Test parsing when some paths are valid format, others aren't."""
        issue_text = '''
        Traceback (most recent call last):
          File "src/app/auth.py", line 10, in get_user_profile
            name = user["name"]
        KeyError: 'name'
        
        Also check src/invalid/path.py:20
        And some random text here
        Target: src/app/utils.py
        '''
        
        paths = _paths_from_issue_text(issue_text)
        expected = [
            ("src/app/auth.py", 10),
            ("src/invalid/path.py", 20),
            ("src/app/utils.py", None)
        ]
        assert paths == expected


class TestIntegrationWithMissingFiles:
    """Integration tests simulating real scenarios with missing files."""
    
    @patch('ticketwatcher.handlers.get_default_branch')
    @patch('ticketwatcher.handlers.file_exists')
    @patch('ticketwatcher.handlers.get_file_text')
    @patch('ticketwatcher.handlers.add_issue_comment')
    def test_issue_with_nonexistent_file_graceful_handling(self, mock_comment, mock_get_file, mock_file_exists, mock_branch):
        """Test full flow when issue references files that don't exist."""
        mock_branch.return_value = "main"
        mock_file_exists.return_value = False  # File doesn't exist
        
        event = {
            "action": "opened",
            "issue": {
                "number": 456,
                "title": "[agent-fix] Error in missing file",
                "body": 'File "src/nonexistent/missing.py", line 5\n  some error',
                "labels": [{"name": "agent-fix"}]
            }
        }
        
        # This should not crash and should handle gracefully
        result = handle_issue_event(event)
        
