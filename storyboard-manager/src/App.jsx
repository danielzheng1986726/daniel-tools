import { useState } from 'react';
import ProjectList from './components/ProjectList.jsx';
import StoryboardEditor from './components/StoryboardEditor.jsx';

export default function App() {
  const [currentProject, setCurrentProject] = useState(null);
  const [clientMode, setClientMode] = useState(false);

  if (currentProject) {
    return (
      <StoryboardEditor
        projectId={currentProject}
        clientMode={clientMode}
        setClientMode={setClientMode}
        onBack={() => { setCurrentProject(null); setClientMode(false); }}
      />
    );
  }

  return <ProjectList onOpen={setCurrentProject} />;
}
