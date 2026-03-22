# 🎨 Tauon AI - UI/UX Modernization Plan

**Version:** 9.1.1-AI-v3  
**Date:** March 19, 2026  
**Status:** Planning Phase

---

## 🐛 **Current UI Issues (Bugs)**

### **Critical Issues:**

#### **1. Empty Submenus**
- ❌ "Generate Playlist…" submenu has only 1 item (Last.fm Radio)
- ❌ Looks broken/incomplete to users
- **Fix:** Either populate with more items or remove the submenu

#### **2. Missing Submenu Indicators**
- ❌ "🎵 Audio Recommendations" doesn't show ">" arrow
- ❌ Users don't know it's expandable
- **Fix:** Ensure `is_sub_menu=True` flag is set correctly

#### **3. Mood Distribution Not Working**
- ❌ Clicking does nothing visible
- ❌ No error message shown
- **Fix:** Add better error handling and console logging

#### **4. Inconsistent Menu Structure**
- ❌ Some items use `pass_ref=True`, others don't
- ❌ Mix of lambda and direct function calls
- ❌ Hardcoded submenu indices (-1, -2, 3, 1)
- **Fix:** Standardize menu creation pattern

---

## 📊 **UI/UX Audit - Current State**

### **Menu Hierarchy Issues:**

```
Current Track Menu (Right-click track):
├─ Generate Playlist… ← Mostly empty!
│  └─ ↯ Last.fm Radio (this artist)
├─ 🎵 Audio Recommendations ← No ">" indicator
│  ├─ 📻 Similarity Radio (this track)
│  ├─ ✦ Mood Playlists (Audio)
│  ├─ ⚡ Energy Playlists
│  ├─ 🎼 Genre Clusters
│  ├─ 📅 Decade Playlists
│  ├─ 👤 Artist Radio (Last.fm)
│  └─ ✦ AI Mood Playlists (Claude/Local) [Legacy]
└─ ⊕ Audio Feature Clusters ← Should be in Audio Recommendations!
```

**Problems:**
1. "Generate Playlist…" is redundant with "Audio Recommendations"
2. "Audio Feature Clusters" is orphaned (should be in Audio Recommendations)
3. No visual hierarchy (all items look the same)
4. Legacy items mixed with new items

### **Proposed Clean Structure:**

```
Proposed Track Menu (Right-click track):
├─ 🎵 Create Similar Playlist
│  ├─ 📻 Similarity Radio (this track)
│  └─ 👤 Artist Radio (Last.fm)
├─ 🎨 Mood & Genre
│  ├─ ✦ Mood Playlists (8 moods)
│  ├─ ⚡ Energy Playlists
│  └─ 🎼 Genre Clusters
├─ 📅 Decade Playlists
├─ 📊 Analyze Moods (show distribution)
└─ ⊕ Audio Feature Clusters [Advanced]
```

---

## 🎨 **Modern UI Design Language**

### **Design Inspiration:**

#### **macOS Big Sur/Monterey Style:**
- ✅ Rounded corners (10px radius)
- ✅ Translucent materials (vibrancy effects)
- ✅ SF Pro font (or system equivalent)
- ✅ Subtle shadows and depth
- ✅ Large, bold headers
- ✅ Minimalist icons

#### **GNOME/Manjaro Style:**
- ✅ Clean, flat design
- ✅ Adaptive colors (system theme integration)
- ✅ Smooth animations
- ✅ Touch-friendly targets (44px minimum)
- ✅ Keyboard navigation

#### **Modern Web Apps (Spotify/Apple Music):**
- ✅ Gradient backgrounds
- ✅ Card-based layouts
- ✅ Smooth transitions
- ✅ Hover effects
- ✅ Progress indicators

---

## 🚀 **UI Modernization Roadmap**

### **Phase 1: Quick Wins** (4-6 hours)

#### **1.1 Fix Menu Issues**
- [ ] Remove "Generate Playlist…" submenu (merge into Audio Recommendations)
- [ ] Add ">" indicators to all submenus
- [ ] Move "Audio Feature Clusters" into Audio Recommendations
- [ ] Group related items with separators
- [ ] Add keyboard shortcuts (Ctrl+M for Mood, Ctrl+E for Energy, etc.)

#### **1.2 Improve Error Feedback**
- [ ] Show errors for mood distribution
- [ ] Add progress indicators for long operations
- [ ] Add "Cancel" button for playlist generation
- [ ] Better toast notifications (colored by type: info/success/error)

#### **1.3 Visual Polish**
- [ ] Add icons to all menu items
- [ ] Color-code mood playlists (match mood colors)
- [ ] Add hover effects
- [ ] Smooth menu animations

---

### **Phase 2: Settings Overhaul** (8-10 hours)

#### **2.1 Dedicated AI Playlist Section**
```
Settings → AI Playlist Generator:
┌────────────────────────────────────────────┐
│  🎵 AI Playlist Generator                  │
├────────────────────────────────────────────┤
│  ☑ Enable AI Features                      │
│                                            │
│  Last.fm Radio:                            │
│  ├─ API Key: [••••••••••••••••]           │
│  ├─ Seed Artist: [____________]           │
│  └─ Track Limit: [60◀──────▶]             │
│                                            │
│  Mood Playlists:                           │
│  ├─ Number of Moods: [8◀──────▶]          │
│  └─ Use Advanced Algorithm: ☑             │
│                                            │
│  Audio Features:                           │
│  ├─ Use Spotify Features: ☐               │
│  └─ Deep Analysis (librosa): ☐            │
│                                            │
│  [Test Connection]  [Reset to Defaults]   │
└────────────────────────────────────────────┘
```

#### **2.2 Visual Mood Selector**
- Interactive Thayer's mood wheel
- Click to select preferred moods
- Real-time preview of mood distribution
- Drag to adjust mood weights

#### **2.3 Feature Toggles**
- One-click enable/disable for each feature
- Performance impact indicators
- Dependency status (✅ numpy, ⚠️ tekore, ❌ librosa)

---

### **Phase 3: Playlist Generation UI** (12-16 hours)

#### **3.1 Generation Dialog**
Instead of just toast notifications:
```
┌────────────────────────────────────────────┐
│  Generating Mood Playlists…                │
├────────────────────────────────────────────┤
│  ⏳ Analyzing library…                      │
│  ████████████░░░░░░░░ 65% (2m 15s)        │
│                                            │
│  Tracks analyzed: 1,247 / 1,920           │
│  Playlists created: 5 / 8                 │
│                                            │
│  [Cancel]                                  │
└────────────────────────────────────────────┘
```

#### **3.2 Preview Before Creating**
- Show first 3-5 tracks per playlist
- "Regenerate" button for individual playlists
- "Merge Playlists" option
- "Export as M3U/XSPF" option

#### **3.3 Post-Generation Actions**
```
┌────────────────────────────────────────────┐
│  ✅ Created 8 mood playlists!              │
├────────────────────────────────────────────┤
│  ✦ Exuberant (127 tracks)                 │
│  ✦ Energetic (234 tracks)                 │
│  ✦ Frantic (45 tracks)                    │
│  ✦ Happy (189 tracks)                     │
│  ✦ Contentment (156 tracks)               │
│  ✦ Calm (298 tracks)                      │
│  ✦ Sad (167 tracks)                       │
│  ✦ Depression (89 tracks)                 │
├────────────────────────────────────────────┤
│  [View All]  [Shuffle All]  [Export…]     │
└────────────────────────────────────────────┘
```

---

### **Phase 4: Mood Visualization** (6-8 hours)

#### **4.1 Interactive Mood Wheel**
```
        Thayer's Mood Wheel
        
            Frantic
         ⚡ 12% (45 tracks)
         
  Energetic              Happy
  ⚡ 23%           😊 18%
  
           Contentment
           😌 15%
```

- Click mood to create playlist
- Hover for detailed stats
- Drag to adjust mood boundaries
- Export as PNG/SVG

#### **4.2 Library Mood Timeline**
- Show how mood changes over time
- "Mood of the day" insights
- Correlation with play counts

#### **4.3 Mood Badges in Playlist View**
- Color-coded badges next to playlist names
- Hover for mood breakdown
- Click to filter by mood

---

### **Phase 5: Advanced Features** (16-20 hours)

#### **5.1 Smart Queue**
- "Magic Queue" button (infinite similar tracks)
- Queue preview panel
- Drag-and-drop reordering
- Auto-DJ mode (continuous similar tracks)

#### **5.2 Mood Transitions**
- Smooth energy/mood progression
- "Warm-up" → "Peak" → "Cool-down" playlists
- BPM-matched transitions

#### **5.3 Party Mode**
- Read crowd energy (manual input)
- Adjust playlist based on time of day
- Request queue (users vote on next track)

---

## 🎨 **Visual Design Specifications**

### **Color Palette:**

#### **Light Theme:**
```
Background: #FFFFFF (pure white)
Secondary: #F5F5F7 (light gray)
Accent: #007AFF (iOS blue)
Success: #34C759 (green)
Warning: #FF9500 (orange)
Error: #FF3B30 (red)
Text Primary: #1D1D1F
Text Secondary: #86868B
```

#### **Dark Theme:**
```
Background: #1C1C1E (almost black)
Secondary: #2C2C2E (dark gray)
Accent: #0A84FF (bright blue)
Success: #30D158 (bright green)
Warning: #FF9F0A (bright orange)
Error: #FF453A (bright red)
Text Primary: #FFFFFF
Text Secondary: #98989D
```

### **Typography:**

```
Headers: 24px, SemiBold, -0.5px tracking
Subheaders: 20px, Medium, -0.3px tracking
Body: 15px, Regular, 0px tracking
Captions: 13px, Regular, 0px tracking
Buttons: 15px, SemiBold, 0px tracking
```

### **Spacing:**

```
Padding (small): 8px
Padding (medium): 16px
Padding (large): 24px
Margin (small): 8px
Margin (medium): 16px
Margin (large): 24px
Border Radius: 10px
Shadow: 0px 4px 16px rgba(0,0,0,0.1)
```

---

## 📋 **Implementation Priority**

### **Immediate (Next Session):**
1. ✅ Fix menu bugs (empty submenus, missing indicators)
2. ✅ Improve error feedback
3. ✅ Add icons to menu items

### **Short-term (1-2 weeks):**
1. Settings overhaul
2. Generation progress dialog
3. Mood visualization improvements

### **Medium-term (1 month):**
1. Interactive mood wheel
2. Smart queue integration
3. Keyboard shortcuts

### **Long-term (2-3 months):**
1. Full visual redesign
2. Touch optimization
3. Advanced features (Party Mode, etc.)

---

## 🐛 **Bug Fix Checklist** (Immediate)

- [ ] Fix "Generate Playlist…" empty submenu
- [ ] Add ">" indicators to submenus
- [ ] Fix mood distribution (show errors)
- [ ] Standardize menu item patterns
- [ ] Add keyboard shortcuts
- [ ] Fix inconsistent pass_ref usage
- [ ] Add loading indicators
- [ ] Improve toast notifications

---

## 📊 **Success Metrics**

### **Usability:**
- [ ] 50% reduction in "feature not found" reports
- [ ] 80% user satisfaction with menu navigation
- [ ] <2 clicks to access any playlist generator

### **Performance:**
- [ ] Menu open time <100ms
- [ ] Playlist generation <5s for 80% of operations
- [ ] No UI freezes during analysis

### **Aesthetics:**
- [ ] Consistent design language across all screens
- [ ] Positive user feedback on modernization
- [ ] Professional, polished appearance

---

**Next Steps:** Start with Phase 1 (Quick Wins) to fix immediate issues, then proceed through phases based on priority and available time.
