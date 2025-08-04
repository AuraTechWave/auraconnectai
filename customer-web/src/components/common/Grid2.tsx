// Temporary wrapper for Grid component to handle MUI v5 Grid API changes
import { Grid, GridProps } from '@mui/material';
import React from 'react';

interface Grid2Props extends Omit<GridProps, 'item' | 'container'> {
  item?: boolean;
  container?: boolean;
  xs?: number | 'auto';
  sm?: number | 'auto';
  md?: number | 'auto';
  lg?: number | 'auto';
  xl?: number | 'auto';
}

export const Grid2: React.FC<Grid2Props> = ({ item, container, xs, sm, md, lg, xl, ...props }) => {
  const gridProps: any = {
    ...props,
  };

  if (container) {
    gridProps.container = true;
  }
  
  if (item) {
    gridProps.item = true;
    if (xs !== undefined) gridProps.xs = xs;
    if (sm !== undefined) gridProps.sm = sm;
    if (md !== undefined) gridProps.md = md;
    if (lg !== undefined) gridProps.lg = lg;
    if (xl !== undefined) gridProps.xl = xl;
  }

  return <Grid {...gridProps} />;
};

export default Grid2;