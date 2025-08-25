import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { promotionsApi, menuApi } from '../../services/api';
import LoadingSpinner from '../../components/customer/LoadingSpinner';
import './HomePage.css';

function HomePage() {
  const { data: promotions, isLoading: promotionsLoading } = useQuery({
    queryKey: ['active-promotions'],
    queryFn: async () => {
      const response = await promotionsApi.getActivePromotions();
      return response.data;
    },
  });

  const { data: featuredItems, isLoading: itemsLoading } = useQuery({
    queryKey: ['featured-items'],
    queryFn: async () => {
      const response = await menuApi.getMenuItems({ featured: true, limit: 6 });
      return response.data;
    },
  });

  return (
    <div className="home-page">
      <section className="hero-section">
        <div className="hero-content">
          <h1>Welcome to AuraConnect</h1>
          <p>Experience the finest dining with our exceptional menu</p>
          <Link to="/menu" className="cta-button">
            Browse Menu
          </Link>
        </div>
      </section>

      {promotionsLoading ? (
        <LoadingSpinner />
      ) : promotions?.length > 0 && (
        <section className="promotions-section">
          <h2>Special Offers</h2>
          <div className="promotions-grid">
            {promotions.slice(0, 3).map((promo) => (
              <div key={promo.id} className="promotion-card">
                <h3>{promo.name}</h3>
                <p>{promo.description}</p>
                {promo.code && (
                  <div className="promo-code">
                    Code: <strong>{promo.code}</strong>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="featured-section">
        <h2>Featured Items</h2>
        {itemsLoading ? (
          <LoadingSpinner />
        ) : (
          <div className="featured-grid">
            {featuredItems?.map((item) => (
              <div key={item.id} className="featured-item">
                {item.image_url && (
                  <img src={item.image_url} alt={item.name} />
                )}
                <h3>{item.name}</h3>
                <p className="item-price">${item.price?.toFixed(2)}</p>
                <Link to="/menu" className="view-item-btn">
                  View Item
                </Link>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="info-section">
        <div className="info-grid">
          <div className="info-card">
            <h3>🚚 Fast Delivery</h3>
            <p>Get your food delivered hot and fresh within 30 minutes</p>
          </div>
          <div className="info-card">
            <h3>📱 Real-time Tracking</h3>
            <p>Track your order status in real-time from kitchen to table</p>
          </div>
          <div className="info-card">
            <h3>🎁 Loyalty Rewards</h3>
            <p>Earn points with every order and redeem exclusive rewards</p>
          </div>
        </div>
      </section>
    </div>
  );
}

export default HomePage;