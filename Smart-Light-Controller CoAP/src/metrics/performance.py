class PerformanceMetrics:
    @staticmethod
    def calculate(protocol_data, inputs):
        nodes = inputs.get('nodes', 10)
        tx_power = inputs.get('tx_power', 10.0)
        
        # Standardized Research Metrics
        accuracy = min(99.4, protocol_data['ch_accuracy'] + (tx_power * 0.1))
        delivery = min(99.8, protocol_data['delivery_ratio'] + (tx_power * 0.2))
        latency = max(5, protocol_data['latency'] - (tx_power * 0.5))
        energy = max(2, protocol_data['energy_consumption'] + (nodes * 0.1))
        overhead = protocol_data['overhead'] + (nodes * 2)

        return {
            'accuracy': round(accuracy, 2),
            'delivery_ratio': round(delivery, 2),
            'latency': round(latency, 1),
            'energy_consumption': round(energy, 2),
            'overhead': round(overhead, 0)
        }
