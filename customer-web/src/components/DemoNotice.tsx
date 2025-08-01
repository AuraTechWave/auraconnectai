import React, { useState } from 'react';
import { Alert, AlertTitle, Collapse, IconButton } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';

const DemoNotice: React.FC = () => {
  const [open, setOpen] = useState(true);

  return (
    <Collapse in={open}>
      <Alert
        severity="info"
        action={
          <IconButton
            aria-label="close"
            color="inherit"
            size="small"
            onClick={() => {
              setOpen(false);
            }}
          >
            <CloseIcon fontSize="inherit" />
          </IconButton>
        }
        sx={{ mb: 2 }}
      >
        <AlertTitle>Demo Mode</AlertTitle>
        This is a demo version of the AuraConnect customer web app. Use these credentials to login:
        <br />
        <strong>Email:</strong> demo@example.com | <strong>Password:</strong> demo123
        <br />
        All data shown is mock data for demonstration purposes.
      </Alert>
    </Collapse>
  );
};

export default DemoNotice;