import pandas as pd
import numpy as np
import os
import sys
import datetime

# Update system path to include parent directories for module access
# This allows the script to import modules from two directories up in the folder hierarchy
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Import specific data and functions from external modules
from _00_shared_functions import column_name_sorter
from _02b_breakout_order_data import broken_out_order_data
from _02a_clean_raw_data import cleaned_deliverect_item_level_detail_data

def output_deliverect_data():
    # Initialize DataFrame for data processing
    # The 'imported_deliverect_item_level_detail_data' is assigned to 'df' for processing
    order_df = broken_out_order_data
    item_df = cleaned_deliverect_item_level_detail_data

    # Create Output DataFrame
    output_df = order_df.copy()

    # Filter to exclude records from before 1st Jan 2023
    filter_date = datetime.date(2023, 1, 1)
    output_df = output_df.loc[output_df['OrderPlacedDate'] >= filter_date]

    # Merge the dataframes together
    output_df = pd.merge(output_df, item_df[['PrimaryKeyItem', 'ItemPrice', 'ItemQuantity']], on='PrimaryKeyItem', how='left')
    output_df['Quantity'] = pd.to_numeric(output_df['Quantity'], errors='coerce')

    # Calculate the total item cost
    output_df['TotalItemCost'] = output_df['ItemPrice'] * output_df['Quantity']

    # Add a running index based on 'PrimaryKeyAlt'
    mask = output_df['PrimaryKeyAlt'] != output_df['PrimaryKeyAlt'].shift()
    output_df['PrimaryKeyIndex'] = (mask.cumsum() + 1).astype(int)
    output_df['PrimaryKeyIndex'] = output_df['PrimaryKeyIndex'] - 1

    # Add an item index within each 'PrimaryKeyAlt' group
    output_df['ItemIndex'] = output_df.groupby('PrimaryKeyAlt').cumcount() + 1

    # Convert required columns to floats
    output_df['PromotionsOnItems'] = output_df['PromotionsOnItems'].astype(float)
    output_df['DriverTip'] = output_df['DriverTip'].astype(float)
    output_df['ItemQuantity'] = output_df['ItemQuantity'].astype(float)

    # Convert to string and then replace empty strings
    output_df['ItemPrice'] = output_df['ItemPrice'].astype(str).replace('', 0)
    output_df['ItemQuantity'] = output_df['ItemQuantity'].astype(str).replace('', 0)
    output_df['TotalItemCost'] = output_df['TotalItemCost'].astype(str).replace('', 0)

    # Convert back to the original (likely numerical) data type
    output_df['ItemPrice'] = pd.to_numeric(output_df['ItemPrice'], errors='coerce')
    output_df['ItemQuantity'] = pd.to_numeric(output_df['ItemQuantity'], errors='coerce')
    output_df['TotalItemCost'] = pd.to_numeric(output_df['TotalItemCost'], errors='coerce')

    # Fill NaN values with zeros
    output_df['ItemPrice'] = output_df['ItemPrice'].fillna(0)
    output_df['ItemQuantity'] = output_df['ItemQuantity'].fillna(0)
    output_df['TotalItemCost'] = output_df['TotalItemCost'].fillna(0)

    # Export the DataFrame to a CSV file for checking
    output_df.to_csv('Final Item Detail Master.csv', index=False)

    return output_df, order_df, item_df

# Call the function and assign the returned DataFrames to variables
output_df, order_df, item_df = output_deliverect_data()

def add_balancing_items():
    # Copying the original DataFrame for safe manipulation without altering the original data
    price_discrepancies_df = output_df.copy()

    # Grouping the data by 'PrimaryKeyAlt' and summing 'TotalItemCost' for each group
    summed_costs = price_discrepancies_df.groupby('PrimaryKeyAlt')[['PrimaryKeyIndex', 'ItemIndex', 'TotalItemCost']].sum().reset_index()

    # Extracting the first occurrence of GrossAOV for each PrimaryKeyAlt
    first_gross_aov = price_discrepancies_df.drop_duplicates(subset='PrimaryKeyAlt')[['PrimaryKeyAlt', 'GrossAOV']]

    # Merging the summed costs and first gross AOV on PrimaryKeyAlt
    merged_df = pd.merge(summed_costs, first_gross_aov, on='PrimaryKeyAlt')

    # Converting GrossAOV and TotalItemCost to float and rounding to 2 decimal places
    merged_df['GrossAOV'] = merged_df['GrossAOV'].astype(float).round(2)
    merged_df['TotalItemCost'] = merged_df['TotalItemCost'].astype(float).round(2)

    # Identifying rows where GrossAOV and TotalItemCost don't match
    merged_df['AOVCheck'] = np.where(merged_df['GrossAOV'] != merged_df['TotalItemCost'], 'Price Discrepancies', '')
    merged_df = merged_df[merged_df['AOVCheck'] == 'Price Discrepancies']

    # Calculating the difference in price
    merged_df['PriceDifference'] = merged_df['GrossAOV'] - merged_df['TotalItemCost']

    # Filtering the original DataFrame to keep only those entries with discrepancies
    price_discrepancies_df = price_discrepancies_df[price_discrepancies_df['PrimaryKeyAlt'].isin(merged_df['PrimaryKeyAlt'])]

    # Selecting only the first item in each group for adjustment
    price_discrepancies_df = price_discrepancies_df.loc[price_discrepancies_df['ItemIndex'] == 1]

    # Merging the price difference information back into the discrepancies DataFrame
    price_discrepancies_df = pd.merge(price_discrepancies_df, merged_df[['PrimaryKeyAlt', 'PriceDifference']], on='PrimaryKeyAlt', how='left')

    # Setting values for the balancing item to adjust discrepancies
    price_discrepancies_df['ProductPLU'] = 'x-xx-xxxx-x'
    price_discrepancies_df['ProductName'] = 'Balancing Item'
    price_discrepancies_df['ItemPrice'] = price_discrepancies_df['PriceDifference']
    price_discrepancies_df['Quantity'] = 1
    price_discrepancies_df['ItemQuantity'] = 1
    price_discrepancies_df['TotalItemCost'] = price_discrepancies_df['PriceDifference']
    price_discrepancies_df['ItemIndex'] = 500

    # Combining the original DataFrame with the adjusted discrepancy rows
    price_discrepancies_output_df = pd.concat([output_df, price_discrepancies_df], ignore_index=True)

    # Sorting the DataFrame based on PrimaryKeyIndex and ItemIndex
    price_discrepancies_output_df.sort_values(by=['PrimaryKeyIndex', 'ItemIndex'], inplace=True)

    # Calling an external function to sort columns
    price_discrepancies_output_df = column_name_sorter(price_discrepancies_output_df)

    # Exporting the processed DataFrame to a CSV file
    price_discrepancies_output_df.to_csv('Processed Item Detail Data With Balancing Items.csv', index=False)

    return price_discrepancies_df

price_discrepancies_output_df = add_balancing_items()
