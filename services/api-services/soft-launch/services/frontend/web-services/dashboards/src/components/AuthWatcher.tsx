import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { clearTokens } from '@/lib/auth';

const AuthWatcher = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const onExpired = () => {
      // clear local auth and navigate to login
      clearTokens();
      navigate('/login');
    };

    window.addEventListener('ntheemba:auth-expired', onExpired as EventListener);
    return () => window.removeEventListener('ntheemba:auth-expired', onExpired as EventListener);
  }, [navigate]);

  return null;
};

export default AuthWatcher;
