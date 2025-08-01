import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Button,
  Box,
  Chip,
  TextField,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Radio,
  RadioGroup,
  Divider,
  IconButton,
  Alert,
} from '@mui/material';
import {
  Close as CloseIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
} from '@mui/icons-material';
import { MenuItemWithDetails, Modifier } from '../../types';
import { useCartStore } from '../../store/cartStore';

interface MenuItemModalProps {
  item: MenuItemWithDetails | null;
  open: boolean;
  onClose: () => void;
}

export const MenuItemModal: React.FC<MenuItemModalProps> = ({ item, open, onClose }) => {
  const { addItem } = useCartStore();
  const [quantity, setQuantity] = useState(1);
  const [selectedModifiers, setSelectedModifiers] = useState<Modifier[]>([]);
  const [specialInstructions, setSpecialInstructions] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (!item) return null;

  const handleModifierChange = (modifier: Modifier, checked: boolean) => {
    if (checked) {
      setSelectedModifiers([...selectedModifiers, modifier]);
    } else {
      setSelectedModifiers(selectedModifiers.filter((m) => m.id !== modifier.id));
    }
    setError(null);
  };

  const handleAddToCart = () => {
    // Validate modifier selections
    const modifierGroups = item.modifiers || [];
    for (const group of modifierGroups) {
      const groupModifiers = selectedModifiers.filter((m) =>
        group.modifiers.some((gm) => gm.id === m.id)
      );
      
      if (group.min_selections && groupModifiers.length < group.min_selections) {
        setError(`Please select at least ${group.min_selections} ${group.name}`);
        return;
      }
      
      if (group.max_selections && groupModifiers.length > group.max_selections) {
        setError(`Please select at most ${group.max_selections} ${group.name}`);
        return;
      }
    }

    addItem(item, quantity, selectedModifiers, specialInstructions);
    handleClose();
  };

  const handleClose = () => {
    setQuantity(1);
    setSelectedModifiers([]);
    setSpecialInstructions('');
    setError(null);
    onClose();
  };

  const calculateTotal = () => {
    const modifierTotal = selectedModifiers.reduce(
      (sum, modifier) => sum + modifier.price_adjustment,
      0
    );
    return ((item.price + modifierTotal) * quantity).toFixed(2);
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h5">{item.name}</Typography>
          <IconButton onClick={handleClose}>
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>
      
      <DialogContent>
        {item.image_url && (
          <Box
            component="img"
            src={item.image_url}
            alt={item.name}
            sx={{
              width: '100%',
              height: 200,
              objectFit: 'cover',
              borderRadius: 1,
              mb: 2,
            }}
          />
        )}

        <Typography variant="body1" color="text.secondary" paragraph>
          {item.description}
        </Typography>

        <Box sx={{ mb: 2 }}>
          <Typography variant="h6" color="primary">
            ${item.price.toFixed(2)}
          </Typography>
        </Box>

        {item.dietary_tags && item.dietary_tags.length > 0 && (
          <Box sx={{ mb: 2 }}>
            {item.dietary_tags.map((tag) => (
              <Chip key={tag} label={tag} size="small" color="success" sx={{ mr: 1 }} />
            ))}
          </Box>
        )}

        {item.allergens && item.allergens.length > 0 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Contains: {item.allergens.join(', ')}
          </Alert>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* Modifiers */}
        {item.modifiers && item.modifiers.length > 0 && (
          <>
            <Divider sx={{ my: 2 }} />
            {item.modifiers.map((group) => (
              <Box key={group.id} sx={{ mb: 3 }}>
                <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                  {group.name}
                  {group.min_selections && (
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                      (Select at least {group.min_selections})
                    </Typography>
                  )}
                </Typography>
                
                {group.max_selections === 1 ? (
                  <RadioGroup>
                    {group.modifiers.map((modifier) => (
                      <FormControlLabel
                        key={modifier.id}
                        control={
                          <Radio
                            checked={selectedModifiers.some((m) => m.id === modifier.id)}
                            onChange={(e) => handleModifierChange(modifier, e.target.checked)}
                            disabled={!modifier.is_available}
                          />
                        }
                        label={
                          <Box
                            sx={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              width: '100%',
                            }}
                          >
                            <Typography>{modifier.name}</Typography>
                            {modifier.price_adjustment > 0 && (
                              <Typography color="text.secondary">
                                +${modifier.price_adjustment.toFixed(2)}
                              </Typography>
                            )}
                          </Box>
                        }
                      />
                    ))}
                  </RadioGroup>
                ) : (
                  <FormGroup>
                    {group.modifiers.map((modifier) => (
                      <FormControlLabel
                        key={modifier.id}
                        control={
                          <Checkbox
                            checked={selectedModifiers.some((m) => m.id === modifier.id)}
                            onChange={(e) => handleModifierChange(modifier, e.target.checked)}
                            disabled={!modifier.is_available}
                          />
                        }
                        label={
                          <Box
                            sx={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              width: '100%',
                            }}
                          >
                            <Typography>{modifier.name}</Typography>
                            {modifier.price_adjustment > 0 && (
                              <Typography color="text.secondary">
                                +${modifier.price_adjustment.toFixed(2)}
                              </Typography>
                            )}
                          </Box>
                        }
                      />
                    ))}
                  </FormGroup>
                )}
              </Box>
            ))}
          </>
        )}

        {/* Special Instructions */}
        <Divider sx={{ my: 2 }} />
        <TextField
          fullWidth
          multiline
          rows={3}
          label="Special Instructions (Optional)"
          value={specialInstructions}
          onChange={(e) => setSpecialInstructions(e.target.value)}
          placeholder="e.g., No onions, extra spicy"
        />

        {/* Quantity */}
        <Box sx={{ display: 'flex', alignItems: 'center', mt: 3 }}>
          <Typography variant="subtitle1" sx={{ mr: 2 }}>
            Quantity:
          </Typography>
          <IconButton
            onClick={() => setQuantity(Math.max(1, quantity - 1))}
            disabled={quantity <= 1}
          >
            <RemoveIcon />
          </IconButton>
          <Typography variant="h6" sx={{ mx: 2, minWidth: 30, textAlign: 'center' }}>
            {quantity}
          </Typography>
          <IconButton onClick={() => setQuantity(quantity + 1)}>
            <AddIcon />
          </IconButton>
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 3 }}>
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleAddToCart}
          startIcon={<AddIcon />}
          disabled={!item.is_available}
        >
          Add to Cart (${calculateTotal()})
        </Button>
      </DialogActions>
    </Dialog>
  );
};