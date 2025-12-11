import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { Card, CardHeader, CardBody, Button, Badge, PageLoader, SkeletonProfile } from '../components/common';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import './Profile.css';

// Profile source constants (match backend)
const PROFILE_SOURCE = {
  GITHUB: 'github',
  RESUME: 'resume',
  MANUAL: 'manual',
};

// Helper to format date
const formatDate = (dateStr) => {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { 
    month: 'short', 
    day: 'numeric', 
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

// Helper to get source display info
const getSourceInfo = (source) => {
  switch (source) {
    case PROFILE_SOURCE.GITHUB:
      return { label: 'From GitHub', variant: 'info', icon: 'GH' };
    case PROFILE_SOURCE.RESUME:
      return { label: 'From Resume', variant: 'primary', icon: 'PDF' };
    case PROFILE_SOURCE.MANUAL:
    default:
      return { label: 'Manual', variant: 'secondary', icon: 'Edit' };
  }
};

export function Profile() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [error, setError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    skills: [],
    experience_level: 'intermediate',
    interests: [],
    preferred_languages: [],
    time_availability: 10,
  });
  const [newSkill, setNewSkill] = useState('');
  const [newInterest, setNewInterest] = useState('');
  const [newLanguage, setNewLanguage] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  
  // Confirmation dialog state
  const [showGitHubConfirm, setShowGitHubConfirm] = useState(false);
  const [showResumeConfirm, setShowResumeConfirm] = useState(false);
  const [pendingResumeFile, setPendingResumeFile] = useState(null);
  
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    try {
      setLoading(true);
      const response = await api.getProfile();
      if (response.data) {
        setProfile(response.data);
        setFormData({
          skills: response.data.skills || [],
          experience_level: response.data.experience_level || 'intermediate',
          interests: response.data.interests || [],
          preferred_languages: response.data.preferred_languages || [],
          time_availability: response.data.time_availability || 10,
        });
      }
      setError(null);
    } catch (err) {
      if (err.response?.status !== 404) {
        console.error('Failed to fetch profile:', err);
        setError('Failed to load profile');
      }
    } finally {
      setLoading(false);
    }
  };

  // State for "already synced" message
  const [showAlreadySynced, setShowAlreadySynced] = useState(false);

  // Check if we need confirmation before syncing from GitHub
  const initiateGitHubSync = () => {
    // If profile exists and is from GitHub, show "already synced" message
    if (profile && profile.profile_source === PROFILE_SOURCE.GITHUB) {
      setShowAlreadySynced(true);
      // Auto-dismiss after 3 seconds
      setTimeout(() => setShowAlreadySynced(false), 3000);
      return;
    }
    
    // If profile exists but not from GitHub, show confirmation
    if (profile) {
      setShowGitHubConfirm(true);
    } else {
      // No profile - sync directly
      handleSyncFromGitHub();
    }
  };

  const handleSyncFromGitHub = async () => {
    setShowGitHubConfirm(false);
    try {
      setSyncing(true);
      await api.createProfileFromGithub(user.github_username);
      await fetchProfile();
    } catch (err) {
      console.error('Failed to sync from GitHub:', err);
      setError('Failed to sync from GitHub');
    } finally {
      setSyncing(false);
    }
  };

  // Check if we need confirmation before uploading resume
  const initiateResumeUpload = (file) => {
    if (!file) return;
    
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are supported');
      return;
    }
    
    if (file.size > 5 * 1024 * 1024) {
      setError('File size must be less than 5MB');
      return;
    }
    
    // If profile exists and is not from resume, show confirmation
    if (profile && profile.profile_source !== PROFILE_SOURCE.RESUME) {
      setPendingResumeFile(file);
      setShowResumeConfirm(true);
    } else {
      // Either no profile or already from resume - upload directly
      handleResumeUpload(file);
    }
  };

  const handleResumeUpload = async (file) => {
    const uploadFile = file || pendingResumeFile;
    if (!uploadFile) return;
    
    setShowResumeConfirm(false);
    setPendingResumeFile(null);
    
    try {
      setUploadingResume(true);
      await api.createProfileFromResume(uploadFile);
      await fetchProfile();
    } catch (err) {
      console.error('Failed to parse resume:', err);
      setError(err.response?.data?.detail || 'Failed to parse resume');
    } finally {
      setUploadingResume(false);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      initiateResumeUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      initiateResumeUpload(e.target.files[0]);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      await api.updateProfile(formData);
      await fetchProfile();
      setIsEditing(false);
    } catch (err) {
      console.error('Failed to save profile:', err);
      setError('Failed to save profile');
    } finally {
      setSaving(false);
    }
  };

  const addTag = (field, value, setValue) => {
    if (value.trim() && !formData[field].includes(value.trim())) {
      setFormData({
        ...formData,
        [field]: [...formData[field], value.trim()],
      });
      setValue('');
    }
  };

  const removeTag = (field, value) => {
    setFormData({
      ...formData,
      [field]: formData[field].filter((v) => v !== value),
    });
  };

  const handleDeleteAccount = async () => {
    try {
      setDeleting(true);
      await api.deleteAccount();
      await logout();
      navigate('/login');
    } catch (err) {
      console.error('Failed to delete account:', err);
      setError('Failed to delete account');
      setShowDeleteConfirm(false);
    } finally {
      setDeleting(false);
    }
  };

  // Get source display info
  const sourceInfo = profile ? getSourceInfo(profile.profile_source) : null;
  const isFromGitHub = profile?.profile_source === PROFILE_SOURCE.GITHUB;
  const lastSyncText = profile?.last_github_sync 
    ? `Last synced: ${formatDate(profile.last_github_sync)}`
    : null;

  return (
    <Layout>
      <div className="profile-page animate-fade-in">
        <header className="profile-header">
          <div>
            <h1>Profile</h1>
            <p>Manage your developer profile for better matching</p>
            {/* Profile Source Indicator */}
            {profile && sourceInfo && (
              <div className="profile-source-indicator">
                <Badge variant={sourceInfo.variant} size="sm">
                  {sourceInfo.icon} {sourceInfo.label}
                </Badge>
                {isFromGitHub && lastSyncText && (
                  <span className="profile-sync-time">{lastSyncText}</span>
                )}
              </div>
            )}
          </div>
          <div className="profile-actions">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            <Button 
              variant="outline" 
              onClick={() => fileInputRef.current?.click()}
              loading={uploadingResume}
            >
              {profile?.profile_source === PROFILE_SOURCE.RESUME ? 'Update Resume' : 'Sync from Resume'}
            </Button>
            <Button 
              variant="outline" 
              onClick={initiateGitHubSync}
              loading={syncing}
              title={isFromGitHub && lastSyncText ? lastSyncText : undefined}
            >
              {isFromGitHub ? 'Resync from GitHub' : 'Sync from GitHub'}
            </Button>
            {!isEditing ? (
              <Button variant="primary" onClick={() => setIsEditing(true)}>
                Edit Profile
              </Button>
            ) : (
              <>
                <Button variant="ghost" onClick={() => setIsEditing(false)}>
                  Cancel
                </Button>
                <Button variant="primary" onClick={handleSave} loading={saving}>
                  Save Changes
                </Button>
              </>
            )}
          </div>
        </header>

        {error && (
          <div className="profile-error">
            <p>{error}</p>
            <Button variant="outline" size="sm" onClick={() => setError(null)}>
              Dismiss
            </Button>
          </div>
        )}

        {showAlreadySynced && (
          <div className="profile-info-message">
            <p>Profile already synced from GitHub</p>
            <span className="profile-info-detail">
              Your profile is currently using data from GitHub. 
              It will automatically resync when you log in.
              {lastSyncText && ` ${lastSyncText}`}
            </span>
          </div>
        )}

        {loading ? (
          <div className="profile-grid">
            <SkeletonProfile className="animate-slide-up stagger-1" />
            <SkeletonProfile className="animate-slide-up stagger-2" />
            <SkeletonProfile className="animate-slide-up stagger-3" />
            <SkeletonProfile className="animate-slide-up stagger-4" />
            <SkeletonProfile className="animate-slide-up stagger-5" />
          </div>
        ) : !profile && !isEditing ? (
          <Card className="profile-empty">
            <CardBody>
              <div className="profile-empty-content">
                <span className="profile-empty-icon">Profile</span>
                <h3>Create Your Profile</h3>
                <p>Choose how you'd like to set up your developer profile for personalized issue recommendations</p>
                
                <div className="profile-create-options">
                  <div className="profile-create-option">
                    <div className="option-icon">GH</div>
                    <h4>From GitHub</h4>
                    <p>Auto-extract skills from your repositories</p>
                    <Button variant="primary" onClick={handleSyncFromGitHub} loading={syncing}>
                      Create from GitHub
                    </Button>
                  </div>
                  
                  <div className="profile-create-option">
                    <div className="option-icon">PDF</div>
                    <h4>From Resume</h4>
                    <p>Extract skills from your PDF resume</p>
                    <div 
                      className={`resume-upload-zone-mini ${dragActive ? 'drag-active' : ''}`}
                      onDragEnter={handleDrag}
                      onDragLeave={handleDrag}
                      onDragOver={handleDrag}
                      onDrop={handleDrop}
                      onClick={() => fileInputRef.current?.click()}
                    >
                      {uploadingResume ? (
                        <span>Parsing...</span>
                      ) : (
                        <span>Upload PDF</span>
                      )}
                    </div>
                  </div>
                  
                  <div className="profile-create-option">
                    <div className="option-icon">Edit</div>
                    <h4>Manual Setup</h4>
                    <p>Add your skills and preferences manually</p>
                    <Button variant="outline" onClick={() => setIsEditing(true)}>
                      Create Manually
                    </Button>
                  </div>
                </div>
              </div>
            </CardBody>
          </Card>
        ) : (
          <div className="profile-grid">
            {/* Skills */}
            <Card className="profile-card animate-slide-up stagger-1">
              <CardHeader>
                <h3>Skills</h3>
              </CardHeader>
              <CardBody>
                {isEditing ? (
                  <div className="tag-input-group">
                    <div className="tag-input-row">
                      <input
                        type="text"
                        placeholder="Add a skill..."
                        value={newSkill}
                        onChange={(e) => setNewSkill(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            addTag('skills', newSkill, setNewSkill);
                          }
                        }}
                      />
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => addTag('skills', newSkill, setNewSkill)}
                      >
                        Add
                      </Button>
                    </div>
                    <div className="tag-list">
                      {formData.skills.map((skill) => (
                        <Badge key={skill} variant="tech" size="md">
                          {skill}
                          <button 
                            className="tag-remove"
                            onClick={() => removeTag('skills', skill)}
                          >
                            ×
                          </button>
                        </Badge>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="tag-list">
                    {(profile?.skills || []).length === 0 ? (
                      <span className="no-data">No skills added</span>
                    ) : (
                      (profile?.skills || []).map((skill) => (
                        <Badge key={skill} variant="tech" size="md">{skill}</Badge>
                      ))
                    )}
                  </div>
                )}
              </CardBody>
            </Card>

            {/* Experience Level */}
            <Card className="profile-card animate-slide-up stagger-2">
              <CardHeader>
                <h3>Experience Level</h3>
              </CardHeader>
              <CardBody>
                {isEditing ? (
                  <div className="radio-group">
                    {['beginner', 'intermediate', 'advanced'].map((level) => (
                      <label key={level} className="radio-option">
                        <input
                          type="radio"
                          name="experience_level"
                          value={level}
                          checked={formData.experience_level === level}
                          onChange={(e) => setFormData({ ...formData, experience_level: e.target.value })}
                        />
                        <span className="radio-label">{level}</span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <Badge 
                    variant={profile?.experience_level || 'intermediate'}
                    size="lg"
                  >
                    {profile?.experience_level || 'Not set'}
                  </Badge>
                )}
              </CardBody>
            </Card>

            {/* Interests */}
            <Card className="profile-card animate-slide-up stagger-3">
              <CardHeader>
                <h3>Interests</h3>
              </CardHeader>
              <CardBody>
                {isEditing ? (
                  <div className="tag-input-group">
                    <div className="tag-input-row">
                      <input
                        type="text"
                        placeholder="Add an interest..."
                        value={newInterest}
                        onChange={(e) => setNewInterest(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            addTag('interests', newInterest, setNewInterest);
                          }
                        }}
                      />
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => addTag('interests', newInterest, setNewInterest)}
                      >
                        Add
                      </Button>
                    </div>
                    <div className="tag-list">
                      {formData.interests.map((interest) => (
                        <Badge key={interest} variant="primary" size="md">
                          {interest}
                          <button 
                            className="tag-remove"
                            onClick={() => removeTag('interests', interest)}
                          >
                            ×
                          </button>
                        </Badge>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="tag-list">
                    {(profile?.interests || []).length === 0 ? (
                      <span className="no-data">No interests added</span>
                    ) : (
                      (profile?.interests || []).map((interest) => (
                        <Badge key={interest} variant="primary" size="md">{interest}</Badge>
                      ))
                    )}
                  </div>
                )}
              </CardBody>
            </Card>

            {/* Preferred Languages */}
            <Card className="profile-card animate-slide-up stagger-4">
              <CardHeader>
                <h3>Preferred Languages</h3>
              </CardHeader>
              <CardBody>
                {isEditing ? (
                  <div className="tag-input-group">
                    <div className="tag-input-row">
                      <input
                        type="text"
                        placeholder="Add a language..."
                        value={newLanguage}
                        onChange={(e) => setNewLanguage(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            addTag('preferred_languages', newLanguage, setNewLanguage);
                          }
                        }}
                      />
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => addTag('preferred_languages', newLanguage, setNewLanguage)}
                      >
                        Add
                      </Button>
                    </div>
                    <div className="tag-list">
                      {formData.preferred_languages.map((lang) => (
                        <Badge key={lang} variant="info" size="md">
                          {lang}
                          <button 
                            className="tag-remove"
                            onClick={() => removeTag('preferred_languages', lang)}
                          >
                            ×
                          </button>
                        </Badge>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="tag-list">
                    {(profile?.preferred_languages || []).length === 0 ? (
                      <span className="no-data">No languages added</span>
                    ) : (
                      (profile?.preferred_languages || []).map((lang) => (
                        <Badge key={lang} variant="info" size="md">{lang}</Badge>
                      ))
                    )}
                  </div>
                )}
              </CardBody>
            </Card>

            {/* Time Availability */}
            <Card className="profile-card animate-slide-up stagger-5">
              <CardHeader>
                <h3>Time Availability</h3>
              </CardHeader>
              <CardBody>
                {isEditing ? (
                  <div className="slider-group">
                    <input
                      type="range"
                      min="0"
                      max="40"
                      value={formData.time_availability}
                      onChange={(e) => setFormData({ ...formData, time_availability: parseInt(e.target.value) })}
                    />
                    <span className="slider-value">{formData.time_availability} hours/week</span>
                  </div>
                ) : (
                  <div className="time-display">
                    <span className="time-value">{profile?.time_availability || 0}</span>
                    <span className="time-label">hours/week</span>
                  </div>
                )}
              </CardBody>
            </Card>
          </div>
        )}

        {/* Delete Account Section */}
        <div className="delete-account-section animate-slide-up">
          <h4>Delete Account</h4>
          <div className="delete-account-content">
            {showDeleteConfirm ? (
              <div className="delete-confirm">
                <p>Are you sure? This will permanently delete:</p>
                <ul>
                  <li>Your profile and settings</li>
                  <li>All saved issues and bookmarks</li>
                  <li>Algorithm training data and models</li>
                  <li>Notes and labels</li>
                </ul>
                <div className="delete-confirm-actions">
                  <Button 
                    variant="danger"
                    onClick={handleDeleteAccount}
                    loading={deleting}
                  >
                    Yes, Delete My Account
                  </Button>
                  <Button 
                    variant="outline"
                    onClick={() => setShowDeleteConfirm(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <>
                <p className="delete-account-description">Permanently delete your account and all associated data. This action cannot be undone.</p>
                <Button 
                  variant="danger"
                  onClick={() => setShowDeleteConfirm(true)}
                >
                  Delete Account
                </Button>
              </>
            )}
          </div>
        </div>

        {/* GitHub Sync Confirmation Modal */}
        {showGitHubConfirm && (
          <div className="profile-modal-overlay" onClick={() => setShowGitHubConfirm(false)}>
            <div className="profile-modal" onClick={(e) => e.stopPropagation()}>
              <div className="profile-modal-header">
                <h3>Replace Profile with GitHub Data?</h3>
                <button className="profile-modal-close" onClick={() => setShowGitHubConfirm(false)}>×</button>
              </div>
              <div className="profile-modal-body">
                <p>Your current profile was created from <strong>{profile?.profile_source === PROFILE_SOURCE.RESUME ? 'a resume' : 'manual edits'}</strong>.</p>
                <p>Syncing from GitHub will <strong>replace</strong> your current skills, languages, and interests with data from your GitHub repositories.</p>
                <p className="profile-modal-warning">Warning: This action will overwrite your existing profile data.</p>
              </div>
              <div className="profile-modal-actions">
                <Button variant="outline" onClick={() => setShowGitHubConfirm(false)}>
                  Cancel
                </Button>
                <Button variant="primary" onClick={handleSyncFromGitHub} loading={syncing}>
                  Yes, Sync from GitHub
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Resume Upload Confirmation Modal */}
        {showResumeConfirm && (
          <div className="profile-modal-overlay" onClick={() => { setShowResumeConfirm(false); setPendingResumeFile(null); }}>
            <div className="profile-modal" onClick={(e) => e.stopPropagation()}>
              <div className="profile-modal-header">
                <h3>Replace Profile with Resume Data?</h3>
                <button className="profile-modal-close" onClick={() => { setShowResumeConfirm(false); setPendingResumeFile(null); }}>×</button>
              </div>
              <div className="profile-modal-body">
                <p>Your current profile was created from <strong>{profile?.profile_source === PROFILE_SOURCE.GITHUB ? 'GitHub' : 'manual edits'}</strong>.</p>
                <p>Uploading a resume will <strong>replace</strong> your current skills, experience level, and preferred languages with data extracted from your resume.</p>
                <p className="profile-modal-warning">Warning: This action will overwrite your existing profile data.</p>
              </div>
              <div className="profile-modal-actions">
                <Button variant="outline" onClick={() => { setShowResumeConfirm(false); setPendingResumeFile(null); }}>
                  Cancel
                </Button>
                <Button variant="primary" onClick={() => handleResumeUpload()} loading={uploadingResume}>
                  Yes, Upload Resume
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}

export default Profile;

