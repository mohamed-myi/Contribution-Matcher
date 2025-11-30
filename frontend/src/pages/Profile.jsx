import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { Card, CardHeader, CardBody, Button, Badge, PageLoader } from '../components/common';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import './Profile.css';

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

  const handleSyncFromGitHub = async () => {
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

  const handleResumeUpload = async (file) => {
    if (!file) return;
    
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are supported');
      return;
    }
    
    if (file.size > 5 * 1024 * 1024) {
      setError('File size must be less than 5MB');
      return;
    }
    
    try {
      setUploadingResume(true);
      await api.createProfileFromResume(file);
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
      handleResumeUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleResumeUpload(e.target.files[0]);
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

  if (loading) {
    return (
      <Layout>
        <PageLoader message="Loading profile..." />
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="profile-page animate-fade-in">
        <header className="profile-header">
          <div>
            <h1>Profile</h1>
            <p>Manage your developer profile for better matching</p>
          </div>
          <div className="profile-actions">
            <Button 
              variant="outline" 
              onClick={handleSyncFromGitHub}
              loading={syncing}
            >
              Sync from GitHub
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

        {!profile && !isEditing ? (
          <Card className="profile-empty">
            <CardBody>
              <div className="profile-empty-content">
                <span className="profile-empty-icon"></span>
                <h3>No Profile Yet</h3>
                <p>Create your developer profile to get personalized issue recommendations</p>
                <div className="profile-empty-actions">
                  <Button variant="primary" onClick={handleSyncFromGitHub} loading={syncing}>
                    Create from GitHub
                  </Button>
                  <Button variant="outline" onClick={() => setIsEditing(true)}>
                    Create Manually
                  </Button>
                </div>
                
                <div className="profile-divider">
                  <span>or upload your resume</span>
                </div>
                
                <div 
                  className={`resume-upload-zone ${dragActive ? 'drag-active' : ''}`}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    onChange={handleFileChange}
                    style={{ display: 'none' }}
                  />
                  {uploadingResume ? (
                    <div className="upload-loading">
                      <span className="upload-spinner"></span>
                      <p>Parsing resume...</p>
                    </div>
                  ) : (
                    <>
                      <span className="upload-icon">PDF</span>
                      <p>Drag & drop your resume here</p>
                      <span className="upload-hint">or click to browse (PDF only, max 5MB)</span>
                    </>
                  )}
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
          <div className="delete-account-content">
            <div className="delete-account-info">
              <h4>Delete Account</h4>
              <p>Permanently delete your account and all associated data. This action cannot be undone.</p>
            </div>
            {showDeleteConfirm ? (
              <div className="delete-confirm">
                <p>Are you sure? This will permanently delete:</p>
                <ul>
                  <li>Your profile and settings</li>
                  <li>All saved issues and bookmarks</li>
                  <li>ML training data and models</li>
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
              <Button 
                variant="danger"
                onClick={() => setShowDeleteConfirm(true)}
              >
                Delete Account
              </Button>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default Profile;

