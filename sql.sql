--
-- Remove field clientId from clients
--
ALTER TABLE `core_clients` DROP COLUMN `clientId`;
--
-- Add field commission_no to clients
--
ALTER TABLE `core_clients` ADD COLUMN `commission_no` varchar(50) NULL;
--
-- Alter field cash_no on cashs
--
ALTER TABLE `core_cashs` MODIFY `cash_no` varchar(50) NULL;
--
-- Alter field commission_no on commissions
--
ALTER TABLE `core_commissions` MODIFY `commission_no` varchar(50) NULL;
--
-- Alter field nsd_no on nsds
--
ALTER TABLE `core_nsds` MODIFY `nsd_no` varchar(50) NULL;
--
-- Alter field purchase_no on purchases
--
ALTER TABLE `core_purchases` MODIFY `purchase_no` varchar(50) NULL;
--
-- Alter field sale_no on sales
--
ALTER TABLE `core_sales` MODIFY `sale_no` varchar(50) NULL;
--
-- Alter field transfer_no on stocktransfers
--
ALTER TABLE `core_stocktransfers` MODIFY `transfer_no` varchar(50) NULL;
--
-- Alter unique_together for cashs (1 constraint(s))
--
ALTER TABLE `core_cashs` ADD CONSTRAINT `core_cashs_client_id_cash_no_4c1fa6ee_uniq` UNIQUE (`client_id`, `cash_no`);
--
-- Alter unique_together for commissions (1 constraint(s))
--
ALTER TABLE `core_commissions` ADD CONSTRAINT `core_commissions_client_id_commission_no_2dba2a50_uniq` UNIQUE (`client_id`, `commission_no`);
--
-- Alter unique_together for nsds (1 constraint(s))
--
ALTER TABLE `core_nsds` ADD CONSTRAINT `core_nsds_client_id_nsd_no_048bc498_uniq` UNIQUE (`client_id`, `nsd_no`);
--
-- Alter unique_together for purchases (1 constraint(s))
--
ALTER TABLE `core_purchases` ADD CONSTRAINT `core_purchases_client_id_purchase_no_23dcecac_uniq` UNIQUE (`client_id`, `purchase_no`);
--
-- Alter unique_together for sales (1 constraint(s))
--
ALTER TABLE `core_sales` ADD CONSTRAINT `core_sales_client_id_sale_no_68144547_uniq` UNIQUE (`client_id`, `sale_no`);
--
-- Alter unique_together for stocktransfers (1 constraint(s))
--
ALTER TABLE `core_stocktransfers` ADD CONSTRAINT `core_stocktransfers_client_id_transfer_no_ecc5d92e_uniq` UNIQUE (`client_id`, `transfer_no`);
--
-- Create index core_nsds_client__df3a1f_idx on field(s) client, is_active, date of model nsds
--
CREATE INDEX `core_nsds_client__df3a1f_idx` ON `core_nsds` (`client_id`, `is_active`, `date`);
