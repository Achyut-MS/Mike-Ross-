// EvidenceGuidedInterview.tsx
// React component for sequential evidence collection

import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface EvidenceTemplate {
  template_id: string;
  name: string;
  description: string;
  priority: 'critical' | 'supportive' | 'optional';
  display_order: number;
  collected: boolean;
  evidence_id?: string;
}

interface EvidenceCategory {
  critical: EvidenceTemplate[];
  supportive: EvidenceTemplate[];
  optional: EvidenceTemplate[];
}

interface UploadProgress {
  [key: string]: {
    status: 'idle' | 'uploading' | 'processing' | 'completed' | 'failed';
    progress: number;
    error?: string;
  };
}

const EvidenceGuidedInterview: React.FC<{ caseId: string }> = ({ caseId }) => {
  const [template, setTemplate] = useState<EvidenceCategory | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress>({});
  const [loading, setLoading] = useState(true);
  
  // Flatten template into ordered list
  const [evidenceItems, setEvidenceItems] = useState<EvidenceTemplate[]>([]);
  
  useEffect(() => {
    fetchEvidenceTemplate();
  }, [caseId]);
  
  const fetchEvidenceTemplate = async () => {
    try {
      const response = await axios.get(`/api/v1/cases/${caseId}/evidence/template`);
      const data = response.data;
      
      setTemplate(data.categories);
      
      // Flatten into ordered list: critical → supportive → optional
      const items = [
        ...data.categories.critical,
        ...data.categories.supportive,
        ...data.categories.optional
      ];
      
      setEvidenceItems(items);
      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch template:', error);
    }
  };
  
  const currentItem = evidenceItems[currentIndex];
  
  const handleFileUpload = async (file: File) => {
    if (!currentItem) return;
    
    const templateId = currentItem.template_id;
    
    // Update progress
    setUploadProgress(prev => ({
      ...prev,
      [templateId]: { status: 'uploading', progress: 0 }
    }));
    
    try {
      // Step 1: Request pre-signed URL
      const presignResponse = await axios.post('/api/v1/evidence/presigned-url', {
        case_id: caseId,
        evidence_type: currentItem.name,
        filename: file.name,
        content_type: file.type,
        file_size: file.size
      });
      
      const { evidence_id, upload_url, upload_fields } = presignResponse.data;
      
      // Step 2: Upload directly to S3
      const formData = new FormData();
      Object.entries(upload_fields).forEach(([key, value]) => {
        formData.append(key, value as string);
      });
      formData.append('file', file);
      
      await axios.post(upload_url, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / (progressEvent.total || 1)
          );
          
          setUploadProgress(prev => ({
            ...prev,
            [templateId]: { status: 'uploading', progress: percentCompleted }
          }));
        }
      });
      
      // Step 3: Notify backend
      await axios.post('/api/v1/evidence/register', {
        evidence_id,
        s3_key: upload_fields.key,
        file_size: file.size,
        content_type: file.type
      });
      
      // Step 4: Poll for processing status
      setUploadProgress(prev => ({
        ...prev,
        [templateId]: { status: 'processing', progress: 100 }
      }));
      
      await pollProcessingStatus(evidence_id, templateId);
      
    } catch (error) {
      console.error('Upload failed:', error);
      setUploadProgress(prev => ({
        ...prev,
        [templateId]: { status: 'failed', progress: 0, error: 'Upload failed' }
      }));
    }
  };
  
  const pollProcessingStatus = async (evidenceId: string, templateId: string) => {
    const maxAttempts = 30; // 30 seconds
    let attempts = 0;
    
    const poll = async (): Promise<void> => {
      try {
        const response = await axios.get(`/api/v1/evidence/${evidenceId}/status`);
        const { processing_status } = response.data;
        
        if (processing_status === 'completed') {
          setUploadProgress(prev => ({
            ...prev,
            [templateId]: { status: 'completed', progress: 100 }
          }));
          
          // Mark item as collected
          setEvidenceItems(prev =>
            prev.map(item =>
              item.template_id === templateId
                ? { ...item, collected: true, evidence_id: evidenceId }
                : item
            )
          );
          
          // Auto-advance to next item after 1 second
          setTimeout(() => {
            if (currentIndex < evidenceItems.length - 1) {
              setCurrentIndex(currentIndex + 1);
            }
          }, 1000);
          
        } else if (processing_status === 'failed') {
          setUploadProgress(prev => ({
            ...prev,
            [templateId]: { 
              status: 'failed', 
              progress: 0, 
              error: 'Processing failed' 
            }
          }));
          
        } else if (attempts < maxAttempts) {
          // Still processing, poll again
          attempts++;
          setTimeout(poll, 1000);
        } else {
          // Timeout
          setUploadProgress(prev => ({
            ...prev,
            [templateId]: { 
              status: 'failed', 
              progress: 0, 
              error: 'Processing timeout' 
            }
          }));
        }
      } catch (error) {
        console.error('Status check failed:', error);
      }
    };
    
    poll();
  };
  
  const handleTextDescription = async (description: string) => {
    if (!currentItem) return;
    
    // Create text-only evidence entry
    try {
      await axios.post('/api/v1/evidence/text-entry', {
        case_id: caseId,
        evidence_type: currentItem.name,
        description: description
      });
      
      // Mark as collected
      setEvidenceItems(prev =>
        prev.map(item =>
          item.template_id === currentItem.template_id
            ? { ...item, collected: true }
            : item
        )
      );
      
      // Advance to next
      if (currentIndex < evidenceItems.length - 1) {
        setCurrentIndex(currentIndex + 1);
      }
    } catch (error) {
      console.error('Text entry failed:', error);
    }
  };
  
  const handleSkip = (reason: 'dont_have' | 'not_sure') => {
    if (!currentItem) return;
    
    // Log skip reason
    axios.post('/api/v1/evidence/skip', {
      case_id: caseId,
      evidence_type: currentItem.name,
      reason: reason
    });
    
    // Advance to next
    if (currentIndex < evidenceItems.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };
  
  const handlePrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };
  
  const handleNext = () => {
    if (currentIndex < evidenceItems.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };
  
  const getProgressStats = () => {
    const collected = evidenceItems.filter(item => item.collected).length;
    const total = evidenceItems.length;
    return {
      collected,
      total,
      percentage: Math.round((collected / total) * 100)
    };
  };
  
  if (loading) {
    return <div className="loading">Loading evidence checklist...</div>;
  }
  
  if (!currentItem) {
    return <EvidenceCompletionScreen caseId={caseId} stats={getProgressStats()} />;
  }
  
  const progressStats = getProgressStats();
  const itemProgress = uploadProgress[currentItem.template_id];
  
  return (
    <div className="evidence-interview-container">
      {/* Progress Header */}
      <div className="progress-header">
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${progressStats.percentage}%` }}
          />
        </div>
        <div className="progress-text">
          {progressStats.collected} of {progressStats.total} items collected
        </div>
      </div>
      
      {/* Current Item Card */}
      <div className="evidence-item-card">
        <div className="item-header">
          <span className={`priority-badge priority-${currentItem.priority}`}>
            {currentItem.priority}
          </span>
          <span className="item-counter">
            {currentIndex + 1} / {evidenceItems.length}
          </span>
        </div>
        
        <h2 className="item-name">{currentItem.name}</h2>
        <p className="item-description">{currentItem.description}</p>
        
        {/* Upload Status */}
        {itemProgress && itemProgress.status !== 'idle' && (
          <div className="upload-status">
            {itemProgress.status === 'uploading' && (
              <div className="status-uploading">
                <div className="spinner" />
                <span>Uploading... {itemProgress.progress}%</span>
              </div>
            )}
            
            {itemProgress.status === 'processing' && (
              <div className="status-processing">
                <div className="spinner" />
                <span>Processing document...</span>
              </div>
            )}
            
            {itemProgress.status === 'completed' && (
              <div className="status-completed">
                <span className="checkmark">✓</span>
                <span>Upload complete!</span>
              </div>
            )}
            
            {itemProgress.status === 'failed' && (
              <div className="status-failed">
                <span className="error-icon">✗</span>
                <span>Error: {itemProgress.error}</span>
              </div>
            )}
          </div>
        )}
        
        {/* Action Buttons */}
        {(!itemProgress || itemProgress.status === 'idle' || itemProgress.status === 'failed') && (
          <div className="action-buttons">
            <FileUploadButton onFileSelect={handleFileUpload} />
            
            <TextDescriptionButton onSubmit={handleTextDescription} />
            
            <button 
              className="btn-skip"
              onClick={() => handleSkip('dont_have')}
            >
              I Don't Have This
            </button>
            
            <button 
              className="btn-skip"
              onClick={() => handleSkip('not_sure')}
            >
              I'm Not Sure
            </button>
          </div>
        )}
      </div>
      
      {/* Navigation */}
      <div className="navigation-buttons">
        <button 
          className="btn-nav" 
          onClick={handlePrevious}
          disabled={currentIndex === 0}
        >
          ← Previous
        </button>
        
        <button 
          className="btn-nav" 
          onClick={handleNext}
          disabled={currentIndex === evidenceItems.length - 1}
        >
          Next →
        </button>
      </div>
      
      {/* Evidence Checklist Sidebar */}
      <div className="checklist-sidebar">
        <h3>Evidence Checklist</h3>
        
        {template && (
          <>
            <ChecklistSection 
              title="Critical" 
              items={template.critical}
              currentItemId={currentItem.template_id}
              onItemClick={(index) => setCurrentIndex(index)}
            />
            
            <ChecklistSection 
              title="Supportive" 
              items={template.supportive}
              currentItemId={currentItem.template_id}
              onItemClick={(index) => setCurrentIndex(template.critical.length + index)}
            />
            
            <ChecklistSection 
              title="Optional" 
              items={template.optional}
              currentItemId={currentItem.template_id}
              onItemClick={(index) => setCurrentIndex(
                template.critical.length + template.supportive.length + index
              )}
            />
          </>
        )}
      </div>
    </div>
  );
};

// Sub-components

const FileUploadButton: React.FC<{ onFileSelect: (file: File) => void }> = ({ onFileSelect }) => {
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  
  const handleClick = () => {
    fileInputRef.current?.click();
  };
  
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onFileSelect(file);
    }
  };
  
  return (
    <>
      <input 
        ref={fileInputRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
      <button className="btn-primary" onClick={handleClick}>
        📎 Upload File
      </button>
    </>
  );
};

const TextDescriptionButton: React.FC<{ onSubmit: (text: string) => void }> = ({ onSubmit }) => {
  const [showModal, setShowModal] = useState(false);
  const [text, setText] = useState('');
  
  const handleSubmit = () => {
    if (text.trim()) {
      onSubmit(text);
      setText('');
      setShowModal(false);
    }
  };
  
  return (
    <>
      <button className="btn-secondary" onClick={() => setShowModal(true)}>
        ✍️ Describe in Text
      </button>
      
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Describe this evidence</h3>
            <textarea 
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder="Describe what you have or remember..."
              rows={6}
              className="text-input"
            />
            <div className="modal-buttons">
              <button className="btn-cancel" onClick={() => setShowModal(false)}>
                Cancel
              </button>
              <button className="btn-submit" onClick={handleSubmit}>
                Submit
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

const ChecklistSection: React.FC<{
  title: string;
  items: EvidenceTemplate[];
  currentItemId: string;
  onItemClick: (index: number) => void;
}> = ({ title, items, currentItemId, onItemClick }) => {
  return (
    <div className="checklist-section">
      <h4>{title}</h4>
      <ul>
        {items.map((item, index) => (
          <li 
            key={item.template_id}
            className={`
              checklist-item 
              ${item.collected ? 'collected' : ''} 
              ${item.template_id === currentItemId ? 'current' : ''}
            `}
            onClick={() => onItemClick(index)}
          >
            <span className="checkbox">
              {item.collected ? '✓' : '○'}
            </span>
            <span className="item-name">{item.name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

const EvidenceCompletionScreen: React.FC<{ 
  caseId: string; 
  stats: { collected: number; total: number; percentage: number } 
}> = ({ caseId, stats }) => {
  const navigate = () => {
    window.location.href = `/cases/${caseId}/timeline`;
  };
  
  return (
    <div className="completion-screen">
      <div className="completion-icon">🎉</div>
      <h2>Evidence Collection Complete!</h2>
      <p>You've provided {stats.collected} out of {stats.total} evidence items.</p>
      
      <div className="completion-stats">
        <div className="stat">
          <span className="stat-value">{stats.percentage}%</span>
          <span className="stat-label">Completion</span>
        </div>
      </div>
      
      <button className="btn-next-step" onClick={navigate}>
        Continue to Timeline →
      </button>
    </div>
  );
};

export default EvidenceGuidedInterview;
